"""The evidence engine (spec section 19).

Its purpose is not to let a model read a filing and form a view. It is to give
one a narrow, checkable task: find the passage where the company explains a
movement the numbers already established, and quote it.

Everything in this package except the model call itself is deterministic, and
that is the design rather than an accident. The **citation validator** decides
whether a quotation is real, and it has to exist before anything is asked of a
model — phase 6's exit criterion is that a gold set contains no invented
citations and no invented numbers, which is a property of the checker, not of
the prompt.
"""

from financial_core.evidence.citations import (
    MIN_QUOTE_CHARS,
    VALIDATOR_VERSION,
    Citation,
    CitationCheck,
    CitationVerdict,
    ClaimCheck,
    all_valid,
    normalise,
    numbers_in,
    validate,
    validate_all,
    validate_claim,
)
from financial_core.evidence.documents import (
    DOCUMENT_VERSION,
    Chunk,
    FilingDocument,
    Section,
    SectionKind,
)
from financial_core.evidence.retrieval import (
    DEFAULT_PASSAGES,
    METRIC_VOCABULARY,
    RETRIEVAL_VERSION,
    RetrievedPassage,
    retrieve,
    score_chunk,
    terms_for,
)
from financial_core.evidence.sectioning import (
    MIN_CHUNK_CHARS,
    TARGET_CHUNK_CHARS,
    build_document,
    chunk_section,
    find_sections,
    to_text,
)

__all__ = [
    "DEFAULT_PASSAGES",
    "DOCUMENT_VERSION",
    "METRIC_VOCABULARY",
    "MIN_CHUNK_CHARS",
    "MIN_QUOTE_CHARS",
    "RETRIEVAL_VERSION",
    "TARGET_CHUNK_CHARS",
    "VALIDATOR_VERSION",
    "Chunk",
    "Citation",
    "CitationCheck",
    "CitationVerdict",
    "ClaimCheck",
    "FilingDocument",
    "RetrievedPassage",
    "Section",
    "SectionKind",
    "all_valid",
    "build_document",
    "chunk_section",
    "find_sections",
    "normalise",
    "numbers_in",
    "retrieve",
    "score_chunk",
    "terms_for",
    "to_text",
    "validate",
    "validate_all",
    "validate_claim",
]
