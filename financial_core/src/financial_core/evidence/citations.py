"""The citation validator (spec section 19, step 6).

**This is the module that makes phase 6 safe**, and it is why it was written
before anything was asked of a model. Phase 6's exit criterion is that a gold
set contains no invented citations and no invented numbers — that is a property
of a checker, not of a prompt. A model asked nicely not to fabricate will still
fabricate; a model whose output is discarded unless every quoted word is found
in the document cannot.

Four things are checked, and a quotation has to pass all of them:

1. **The passage exists.** The claimed span is inside the document.
2. **The words are the document's.** The quotation matches the text at that
   span, once whitespace is normalised. Not "resembles" — matches.
3. **It comes from somewhere an explanation lives.** A sentence lifted from the
   risk factors is not a company explaining a movement.

Whitespace is the only thing normalised away. Everything else — wording,
punctuation, digits — must be the filing's own.

**Numbers are checked separately, on the model's own prose, and against the
passages it cited rather than the whole filing.** Both halves of that were
corrections, and both are worth recording.

The check does not belong on the quotation: if a quotation must match the
document exactly, a quotation with a tampered figure already fails as *text not
found*, and a number check over it can never fire. The dangerous invented number
is in the sentence the model writes *around* the quote — "cash conversion fell
because of a $450 million inventory build", where the quotation is genuine and
the $450 million is not.

And the scope cannot be the document. Measured against a real 285,000-character
10-Q, "$450 million" passed, because the digits `450` occur somewhere in it —
as they will for almost any three-digit number. A claim is a statement about the
evidence offered for it, so the evidence is what it is checked against.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from financial_core.evidence.documents import FilingDocument, SectionKind

VALIDATOR_VERSION: Final[str] = "v1"

_WHITESPACE = re.compile(r"\s+")

# A number as a filing writes one: 1,234.5 or 12.3 or 7. The percent and
# currency symbols around it are punctuation and are checked as part of the
# quotation, not here.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Short quotations are not worth validating and are trivially satisfiable by
# accident: "revenue" appears in every filing. A citation has to be a claim.
MIN_QUOTE_CHARS: Final[int] = 40


class CitationVerdict(StrEnum):
    """Whether a quotation may be shown to a reader."""

    VALID = "valid"

    SPAN_OUT_OF_RANGE = "span_out_of_range"
    """The claimed location is not inside the document."""

    TEXT_NOT_FOUND = "text_not_found"
    """The quoted words are not in the document at the claimed span, and not
    anywhere else in it either. The plainest form of a fabricated citation."""

    MISPLACED = "misplaced"
    """The words are in the document, but not where the citation says. Recorded
    separately because it is a different failure: the model found something real
    and reported its position wrongly."""

    TOO_SHORT = "too_short"
    """Too little text to be a claim about anything."""

    NOT_EXPLANATORY = "not_explanatory"
    """Quoted from a part of the filing where an explanation does not live."""


@dataclass(frozen=True, slots=True)
class Citation:
    """A quotation a model claims to have taken from a filing."""

    quote: str
    start: int
    end: int
    section_kind: SectionKind | None = None


@dataclass(frozen=True, slots=True)
class CitationCheck:
    """Whether a quotation survived validation, and why not if it did not."""

    verdict: CitationVerdict
    citation: Citation
    found_at: int | None = None
    """Where the words actually are, when they are in the document at all."""
    version: str = VALIDATOR_VERSION

    @property
    def is_valid(self) -> bool:
        return self.verdict is CitationVerdict.VALID


def normalise(text: str) -> str:
    """Collapse whitespace. The only difference a citation may have.

    A filing's markup puts line breaks and non-breaking spaces wherever the
    layout needed them, and a model reading the text will not reproduce them.
    Wording, punctuation and digits are not touched.
    """
    return _WHITESPACE.sub(" ", text).strip()


def numbers_in(text: str) -> set[str]:
    """Every figure in a passage, with separators removed so 1,234 == 1234."""
    return {match.group(0).replace(",", "") for match in _NUMBER.finditer(text)}


def validate(citation: Citation, document: FilingDocument) -> CitationCheck:
    """Check one quotation against the document it claims to come from.

    Order matters. Length is checked first because a two-word quotation is
    satisfiable by accident and validating it would give false assurance.
    Numbers are checked last, on a quotation already known to be the document's
    own words, so an invented figure is unambiguous rather than a symptom of
    quoting the wrong passage.
    """
    quote = normalise(citation.quote)

    if len(quote) < MIN_QUOTE_CHARS:
        return CitationCheck(verdict=CitationVerdict.TOO_SHORT, citation=citation)

    if citation.section_kind is not None and not citation.section_kind.is_explanatory:
        return CitationCheck(verdict=CitationVerdict.NOT_EXPLANATORY, citation=citation)

    if not (0 <= citation.start < citation.end <= len(document.text)):
        return CitationCheck(verdict=CitationVerdict.SPAN_OUT_OF_RANGE, citation=citation)

    at_span = normalise(document.excerpt(citation.start, citation.end))
    haystack = normalise(document.text)

    if quote not in at_span:
        # The words may still be the document's, reported at the wrong place.
        # Distinguishing the two matters: one is a fabrication and the other is
        # a bookkeeping error, and only the first impugns the quotation.
        elsewhere = haystack.find(quote)
        if elsewhere == -1:
            return CitationCheck(verdict=CitationVerdict.TEXT_NOT_FOUND, citation=citation)
        return CitationCheck(
            verdict=CitationVerdict.MISPLACED, citation=citation, found_at=elsewhere
        )

    return CitationCheck(
        verdict=CitationVerdict.VALID,
        citation=citation,
        found_at=citation.start,
    )


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    """Whether the model's own sentence may be shown.

    A claim is prose the model wrote, not words it copied, and that is exactly
    where a fabricated figure hides. The quotation beside it can be immaculate
    while the sentence says "a $450 million inventory build" about a document
    that mentions no such number.
    """

    claim: str
    invented_numbers: tuple[str, ...] = ()
    version: str = VALIDATOR_VERSION

    @property
    def is_valid(self) -> bool:
        return not self.invented_numbers


def validate_claim(claim: str, evidence: Sequence[str]) -> ClaimCheck:
    """Every figure in the model's sentence must appear in the evidence it cited.

    Phase 6's exit criterion in one function. A model may summarise, paraphrase
    and connect — it may not introduce a number, because a reader cannot tell an
    introduced one from a quoted one.

    `evidence` is the passages the model cited, not the filing. Checking against
    the whole document is no check at all: in a real 285,000-character 10-Q the
    digits of almost any three-digit figure occur somewhere.
    """
    supported = set()
    for passage in evidence:
        supported |= numbers_in(passage)
    invented = tuple(sorted(numbers_in(claim) - supported))
    return ClaimCheck(claim=claim, invented_numbers=invented)


def validate_all(citations: list[Citation], document: FilingDocument) -> list[CitationCheck]:
    """Check every quotation. Nothing is accepted on the strength of another."""
    return [validate(citation, document) for citation in citations]


def all_valid(checks: list[CitationCheck], claim: ClaimCheck | None = None) -> bool:
    """Whether a finding may be published.

    Every citation, not most of them. A finding with one fabricated quotation
    among four is not three-quarters trustworthy — it is evidence that the model
    was willing to fabricate, which disqualifies the rest. A claim carrying an
    invented figure fails the whole finding for the same reason.
    """
    if claim is not None and not claim.is_valid:
        return False
    return bool(checks) and all(check.is_valid for check in checks)
