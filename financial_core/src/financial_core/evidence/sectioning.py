"""Turning a filing into sections and chunks.

Pure: HTML in, text and offsets out. No network, no model, no clock.

Two rules shape everything here.

**Offsets must survive.** Every transformation from markup to text is applied in
a way that leaves the result indexable, because the citation validator's whole
job is to look up a quoted span and confirm the words are there. A pipeline that
loses positions turns citation checking into fuzzy matching, and fuzzy matching
against a document that says "cash flow" two hundred times accepts nearly
anything.

**Sections are recognised, never assumed.** A filing whose headings do not match
is one long `OTHER` section rather than a guess at where Item 2 starts. The
retriever then finds nothing and the finding stays `no_evidence`, which is a
truthful outcome; inventing a boundary would put the model in the wrong part of
the document and let it quote confidently from it.
"""

import re
from typing import Final

from financial_core.evidence.documents import Chunk, FilingDocument, Section, SectionKind

# Roughly a page of prose. Long enough to carry an explanation with its context,
# short enough that a model is not handed a chapter and asked to find a sentence.
TARGET_CHUNK_CHARS: Final[int] = 1_800
MIN_CHUNK_CHARS: Final[int] = 200

_SCRIPT_OR_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BLOCK_END = re.compile(r"</(p|div|tr|table|h[1-6]|li|section|br)\s*>|<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")

_ENTITIES: Final[dict[str, str]] = {
    "nbsp": " ",
    "amp": "&",
    "lt": "<",
    "gt": ">",
    "quot": '"',
    "apos": "'",
    "rsquo": "’",
    "lsquo": "‘",
    "ldquo": "“",
    "rdquo": "”",
    "mdash": "—",
    "ndash": "–",
    "hellip": "…",
}

# Headings that name a part of a filing. Ordered most specific first: "Item 7A"
# is market risk and must not be swallowed by the rule for "Item 7".
_HEADING_PATTERNS: Final[tuple[tuple[re.Pattern[str], SectionKind], ...]] = (
    (
        re.compile(r"^\s*item\s+7a\b.*?(quantitative|qualitative|market\s+risk)", re.IGNORECASE),
        SectionKind.OTHER,
    ),
    (
        re.compile(r"^\s*item\s+(2|7)\b[^\n]{0,80}?management.{0,5}s\s+discussion", re.IGNORECASE),
        SectionKind.MANAGEMENT_DISCUSSION,
    ),
    (
        re.compile(r"^\s*management.{0,5}s\s+discussion\s+and\s+analysis", re.IGNORECASE),
        SectionKind.MANAGEMENT_DISCUSSION,
    ),
    (
        re.compile(
            r"^\s*(note\s+\d+|notes\s+to\s+(the\s+)?(consolidated\s+)?financial)", re.IGNORECASE
        ),
        SectionKind.NOTES,
    ),
    (
        re.compile(r"^\s*(segment|reportable\s+segment)", re.IGNORECASE),
        SectionKind.SEGMENT,
    ),
    (
        re.compile(r"^\s*(consolidated\s+)?(statements?\s+of|balance\s+sheets?)", re.IGNORECASE),
        SectionKind.FINANCIAL_STATEMENTS,
    ),
    (re.compile(r"^\s*item\s+\d+[a-z]?\b", re.IGNORECASE), SectionKind.OTHER),
    (re.compile(r"^\s*part\s+[ivx]+\b", re.IGNORECASE), SectionKind.OTHER),
)


def _expand_entity(match: re.Match[str]) -> str:
    """Replace an entity with a single character where possible.

    Same-length replacement is not required — offsets are taken *after* all
    normalisation, against the final text — but collapsing to one character
    keeps the result readable, which matters when a human checks a citation.
    """
    body = match.group(1)
    if body.startswith("#x") or body.startswith("#X"):
        try:
            return chr(int(body[2:], 16))
        except ValueError:
            return " "
    if body.startswith("#"):
        try:
            return chr(int(body[1:]))
        except ValueError:
            return " "
    return _ENTITIES.get(body.lower(), " ")


def to_text(markup: str) -> str:
    """Normalised text of a filing.

    The unit of truth for everything downstream. Block-level tags become line
    breaks so headings stay on their own lines and can be recognised; every
    other tag disappears.
    """
    without_code = _SCRIPT_OR_STYLE.sub(" ", markup)
    with_breaks = _BLOCK_END.sub("\n", without_code)
    without_tags = _TAG.sub(" ", with_breaks)
    decoded = _ENTITY.sub(_expand_entity, without_tags)
    spaced = _WHITESPACE.sub(" ", decoded)
    lines = [line.strip() for line in spaced.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def find_sections(text: str) -> tuple[Section, ...]:
    """Recognise the named parts of a filing.

    A line that matches no heading pattern belongs to whatever section preceded
    it. A document where nothing matches becomes one `OTHER` section, and the
    retriever will find nothing in it — which is the honest outcome rather than
    a guess at where Item 2 begins.
    """
    boundaries: list[tuple[int, SectionKind, str]] = []
    offset = 0
    for line in text.split("\n"):
        stripped = line.strip()
        # A heading is short. A paragraph that opens with "Item 2" is prose.
        if 3 <= len(stripped) <= 120:
            for pattern, kind in _HEADING_PATTERNS:
                if pattern.search(stripped):
                    boundaries.append((offset, kind, stripped))
                    break
        offset += len(line) + 1

    if not boundaries:
        return (Section(kind=SectionKind.OTHER, heading="", start=0, end=len(text)),)

    sections: list[Section] = []
    if boundaries[0][0] > 0:
        sections.append(Section(kind=SectionKind.OTHER, heading="", start=0, end=boundaries[0][0]))
    for index, (start, kind, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(text)
        sections.append(Section(kind=kind, heading=heading, start=start, end=end))
    return tuple(sections)


def chunk_section(section: Section, text: str, first_ordinal: int) -> list[Chunk]:
    """Split one section into passages, on paragraph boundaries.

    Paragraphs are never cut in half. A sentence that explains a movement is
    usually the second half of a paragraph whose first half sets it up, and
    splitting between them hands the model a fragment that reads as a
    non-sequitur.
    """
    body = text[section.start : section.end]
    if not body.strip():
        return []

    chunks: list[Chunk] = []
    ordinal = first_ordinal
    buffer_start = section.start
    cursor = section.start

    for paragraph in body.split("\n"):
        line_length = len(paragraph) + 1
        held = cursor + line_length - buffer_start

        if held >= TARGET_CHUNK_CHARS:
            end = min(cursor + line_length, section.end)
            passage = text[buffer_start:end].strip()
            if len(passage) >= MIN_CHUNK_CHARS:
                chunks.append(
                    Chunk(
                        ordinal=ordinal,
                        section_kind=section.kind,
                        heading=section.heading,
                        text=passage,
                        start=buffer_start,
                        end=end,
                    )
                )
                ordinal += 1
            buffer_start = end
        cursor += line_length

    remainder = text[buffer_start : section.end].strip()
    if len(remainder) >= MIN_CHUNK_CHARS:
        chunks.append(
            Chunk(
                ordinal=ordinal,
                section_kind=section.kind,
                heading=section.heading,
                text=remainder,
                start=buffer_start,
                end=section.end,
            )
        )
    return chunks


def build_document(
    markup: str,
    *,
    filing_reference: str,
    source_url: str,
) -> FilingDocument:
    """A filing, reduced to sections and chunks with their offsets."""
    text = to_text(markup)
    sections = find_sections(text)

    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(chunk_section(section, text, len(chunks)))

    warnings: list[str] = []
    if not any(section.kind.is_explanatory for section in sections):
        warnings.append("no_explanatory_section_recognised")
    if not text.strip():
        warnings.append("document_has_no_text")

    return FilingDocument(
        filing_reference=filing_reference,
        source_url=source_url,
        text=text,
        sections=sections,
        chunks=tuple(chunks),
        warnings=tuple(warnings),
    )
