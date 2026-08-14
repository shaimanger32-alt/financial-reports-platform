"""The document model the evidence engine reads from (spec section 19).

Everything here exists to make one promise enforceable: **a citation can be
checked**. Phase 6's exit criterion is that a gold set contains no invented
citations and no invented numbers, and the only way to hold a model to that is
to be able to look up what it quoted and confirm the words are there.

So a chunk is not just text. It carries the exact character offsets it occupies
in the document's normalised text, which means a quoted passage can be verified
as a real substring at a known location rather than merely resembling one.
Without offsets the validator would be reduced to fuzzy matching, and fuzzy
matching against a document that mentions "cash flow" two hundred times accepts
almost anything.

The normalised text is the unit of truth, not the HTML. A filing's markup
changes between filers and between years; the words do not.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

DOCUMENT_VERSION: Final[str] = "v1"


class SectionKind(StrEnum):
    """What part of a filing a section is.

    Only the parts an explanation plausibly lives in are named. Section 19 is
    explicit that the model gets "a narrow, controlled task", and pointing it at
    the risk factors when the question is why collection lengthened is neither
    narrow nor controlled.
    """

    MANAGEMENT_DISCUSSION = "management_discussion"
    """Item 2 in a 10-Q, Item 7 in a 10-K. Where a company explains itself."""

    NOTES = "notes"
    """Notes to the financial statements. Where the detail behind a line is."""

    SEGMENT = "segment"
    """Segment reporting and its commentary."""

    FINANCIAL_STATEMENTS = "financial_statements"
    """The statements themselves. Useful for confirming a figure, not for why."""

    OTHER = "other"
    """Everything else — cover pages, controls, legal proceedings, signatures.
    Kept so offsets stay continuous, and excluded from retrieval."""

    @property
    def is_explanatory(self) -> bool:
        """Whether an explanation of a numeric change plausibly lives here."""
        return self in {
            SectionKind.MANAGEMENT_DISCUSSION,
            SectionKind.NOTES,
            SectionKind.SEGMENT,
        }


@dataclass(frozen=True, slots=True)
class Chunk:
    """A passage of a filing, with its exact place in the document.

    `start` and `end` index into the document's normalised text. They are what
    the citation validator uses, and they are why a quotation can be proved
    rather than believed.
    """

    ordinal: int
    section_kind: SectionKind
    heading: str
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"chunk {self.ordinal} has an impossible span")

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Section:
    """One named part of a filing."""

    kind: SectionKind
    heading: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class FilingDocument:
    """One filing, reduced to text a retriever and a validator can work over."""

    filing_reference: str
    """The accession number, so any passage traces back to a real document."""
    source_url: str
    text: str
    """Normalised text. The unit of truth: markup differs between filers and
    between years, and the words do not."""
    sections: tuple[Section, ...] = ()
    chunks: tuple[Chunk, ...] = ()
    version: str = DOCUMENT_VERSION
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def explanatory_chunks(self) -> tuple[Chunk, ...]:
        """Chunks an explanation plausibly lives in."""
        return tuple(chunk for chunk in self.chunks if chunk.section_kind.is_explanatory)

    def excerpt(self, start: int, end: int) -> str:
        """The document's own words at a span. The validator's ground truth."""
        return self.text[start:end]
