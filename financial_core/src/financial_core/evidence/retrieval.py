"""Finding the passages that might explain a numeric finding (spec section 19).

Deterministic, and with no embedding model behind it. That is a considered
choice rather than a shortcut:

* It adds no dependency and no second model to keep in step with the first.
* It is **explainable** — a passage was retrieved because it contains these
  words, which is a sentence a person can check. "The vectors were close" is
  not.
* It is reproducible. Section 23 requires two readers a month apart to see the
  same answer, and a re-embedded corpus does not guarantee that.

The vocabulary is data, like every other analytical rule in this system, and it
is per **metric** rather than per signal: what a company calls the thing that
moved does not depend on which direction it moved in.

Retrieval never decides anything. It narrows a 285,000-character filing to a few
passages so the model receives "a narrow, controlled task" as section 19 asks.
Whether any of them actually explains anything is the model's answer and the
validator's to check.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from financial_core.evidence.documents import Chunk, FilingDocument

RETRIEVAL_VERSION: Final[str] = "v1"

# How many passages a model is given. Few enough that the task stays narrow,
# more than one so a single unlucky match is not the only candidate.
DEFAULT_PASSAGES: Final[int] = 6

_WORD = re.compile(r"[a-z]+")

# What an issuer calls each thing, in its own words rather than ours. `DSO` is
# our name; a filing says "days sales outstanding" or, far more often, just
# talks about collections and receivables.
METRIC_VOCABULARY: Final[dict[str, tuple[str, ...]]] = {
    "revenue": ("revenue", "sales", "net sales", "top line", "demand", "volume", "pricing"),
    "revenue_growth_yoy": ("revenue", "sales", "growth", "demand", "volume", "organic"),
    "gross_margin": ("gross margin", "gross profit", "cost of sales", "cost of products", "mix"),
    "operating_margin": ("operating margin", "operating income", "operating expenses", "margin"),
    "net_margin": ("net income", "net margin", "profitability"),
    "operating_profit": ("operating income", "operating profit", "segment profit"),
    "net_income": ("net income", "earnings", "profit"),
    "effective_tax_rate": (
        "effective tax rate",
        "income tax",
        "tax expense",
        "valuation allowance",
    ),
    "cash_conversion": (
        "cash flow from operations",
        "operating cash flow",
        "cash conversion",
        "working capital",
    ),
    "accruals_proxy": ("accrual", "operating cash flow", "net income", "working capital"),
    "operating_cash_flow": (
        "cash provided by operating activities",
        "operating cash flow",
        "cash flow from operations",
        "working capital",
    ),
    "operating_cash_flow_growth_yoy": (
        "cash provided by operating activities",
        "operating cash flow",
        "working capital",
        "timing",
    ),
    "days_sales_outstanding": (
        "accounts receivable",
        "receivables",
        "collection",
        "days sales outstanding",
        "credit terms",
        "customer payment",
    ),
    "receivables_growth_gap": ("accounts receivable", "receivables", "collection", "billings"),
    "inventory_growth_gap": ("inventory", "inventories", "stock levels", "supply"),
    "days_inventory_outstanding": ("inventory", "inventories", "turns", "supply chain"),
    "current_ratio": ("liquidity", "current assets", "current liabilities", "working capital"),
    "quick_ratio": ("liquidity", "current assets", "current liabilities"),
    "liabilities_to_equity": ("leverage", "debt", "borrowings", "capital structure"),
    "equity_ratio": ("equity", "capital structure", "shareowners", "stockholders"),
    "net_debt": ("debt", "borrowings", "notes payable", "senior notes", "repayment"),
    "dilution_yoy": ("shares outstanding", "dilution", "share repurchase", "equity awards"),
}

# Words too common in a filing to carry any signal. Matching on them retrieves
# the cover page.
_NOISE: Final[frozenset[str]] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "was",
        "were",
        "are",
        "our",
        "its",
        "has",
        "have",
        "had",
        "not",
        "may",
        "will",
        "which",
        "such",
        "other",
        "company",
        "quarter",
        "year",
        "period",
        "three",
        "six",
        "nine",
        "months",
        "ended",
        "million",
        "billion",
        "compared",
        "primarily",
        "due",
        "increase",
        "decrease",
    }
)


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """One candidate passage, and why it was chosen."""

    chunk: Chunk
    score: float
    matched_terms: tuple[str, ...]
    """The terms that put it here. This is the explanation of the retrieval, and
    it is why an embedding was not used: a person can check this."""

    @property
    def is_explanatory_section(self) -> bool:
        return self.chunk.section_kind.is_explanatory


def terms_for(metric_code: str) -> tuple[str, ...]:
    """The words an issuer uses for this metric. Empty when we have none."""
    return METRIC_VOCABULARY.get(metric_code, ())


def score_chunk(chunk: Chunk, terms: Sequence[str]) -> tuple[float, tuple[str, ...]]:
    """How well a passage matches a vocabulary.

    A multi-word phrase counts for more than a bare word, because "days sales
    outstanding" appearing together says far more than three common words each
    appearing somewhere.
    """
    haystack = chunk.text.lower()
    matched: list[str] = []
    score = 0.0

    for term in terms:
        if term in _NOISE:
            continue
        if term not in haystack:
            continue
        matched.append(term)
        score += 2.0 if " " in term else 1.0

    if not matched:
        return 0.0, ()

    # Longer passages contain more words by accident. Normalising by length
    # stops a chapter from outranking the paragraph that actually says it.
    words = len(_WORD.findall(haystack)) or 1
    return score * (1.0 + 200.0 / words), tuple(matched)


def retrieve(
    document: FilingDocument,
    metric_code: str,
    limit: int = DEFAULT_PASSAGES,
) -> list[RetrievedPassage]:
    """The passages most likely to discuss one metric.

    Only sections an explanation plausibly lives in are searched. Pointing a
    model at the risk factors when the question is why collection lengthened is
    neither narrow nor controlled, and section 19 asks for both.

    An empty result is a real answer: it means the filing does not appear to
    discuss this, and the finding stays without an explanation rather than
    acquiring a bad one.
    """
    terms = terms_for(metric_code)
    if not terms:
        return []

    scored: list[RetrievedPassage] = []
    for chunk in document.explanatory_chunks:
        score, matched = score_chunk(chunk, terms)
        if score > 0:
            scored.append(RetrievedPassage(chunk=chunk, score=score, matched_terms=matched))

    scored.sort(key=lambda passage: (-passage.score, passage.chunk.ordinal))
    return scored[:limit]
