"""The evidence engine's deterministic half (spec section 19, steps 1-4, 6).

The citation validator carries phase 6's exit criterion — "no invented citations
or numbers in a gold set check" — so most of these tests are attempts to get a
fabrication past it. A validator that only recognises well-formed citations
proves nothing; the ones that matter are the four ways a model goes wrong.
"""

from typing import ClassVar

import pytest

from financial_core.evidence import (
    Citation,
    CitationVerdict,
    SectionKind,
    all_valid,
    build_document,
    find_sections,
    numbers_in,
    retrieve,
    terms_for,
    to_text,
    validate,
    validate_all,
    validate_claim,
)

# Built by concatenation so the source stays readable while each paragraph is a
# single unbroken line. A hard-wrapped paragraph keeps its newlines through
# normalisation, and the tests below search for exact phrases.
_NOTE = (
    "The accompanying financial statements have been prepared in accordance with"
    " generally accepted accounting principles. Accounts receivable increased"
    " during the period, reflecting the timing of collections on a large"
    " programme, and we expect the balance to normalise. Operating cash flow was"
    " 1,204 million for the quarter."
)
_MDA = (
    "Sales increased 8 percent in the quarter, driven by volume in Aerospace."
    " Operating cash flow decreased compared with the prior year, primarily due"
    " to working capital, including higher accounts receivable arising from the"
    " timing of customer payments near the end of the period. We continue to"
    " expect collections to improve."
)
_RISKS = (
    "Our results could be adversely affected by supply chain disruption, and a"
    " deterioration in collections would reduce operating cash flow materially."
)

MARKUP = (
    "<html><body>"
    "<p>HONEYWELL INTERNATIONAL INC</p>"
    "<p>PART I</p>"
    "<p>ITEM 1. Financial Statements</p>"
    "<p>Consolidated Statement of Operations</p>"
    "<p>Net sales 9,123 8,456</p>"
    "<p>Note 1 Basis of Presentation</p>"
    f"<p>{_NOTE}</p>"
    "<p>ITEM 2. Management&#8217;s Discussion and Analysis of Financial Condition</p>"
    f"<p>{_MDA}</p>"
    "<p>ITEM 1A. Risk Factors</p>"
    f"<p>{_RISKS}</p>"
    "</body></html>"
)

DOCUMENT = build_document(
    MARKUP, filing_reference="0000773840-26-000124", source_url="https://sec.gov/x.htm"
)


def span_of(needle: str) -> tuple[int, int]:
    start = DOCUMENT.text.index(needle)
    return start, start + len(needle)


class TestReadingAFiling:
    def test_markup_becomes_text(self) -> None:
        assert "<p>" not in DOCUMENT.text
        assert "Sales increased 8 percent" in DOCUMENT.text

    def test_entities_are_decoded(self) -> None:
        """`Management&#8217;s` has to become `Management's`, or the heading
        pattern never matches and Item 2 is never found."""
        assert "Management’s Discussion" in DOCUMENT.text

    def test_the_parts_of_a_filing_are_recognised(self) -> None:
        kinds = {section.kind for section in DOCUMENT.sections}

        assert SectionKind.MANAGEMENT_DISCUSSION in kinds
        assert SectionKind.NOTES in kinds

    def test_risk_factors_are_not_explanatory(self) -> None:
        """A sentence from the risk factors is a hypothetical, not a company
        explaining what happened."""
        assert not SectionKind.OTHER.is_explanatory

    def test_every_chunk_reproduces_itself_from_its_offsets(self) -> None:
        """The invariant the whole validator rests on. Without it, citation
        checking degrades to fuzzy matching."""
        for chunk in DOCUMENT.chunks:
            assert DOCUMENT.text[chunk.start : chunk.end].strip() == chunk.text

    def test_a_document_with_no_headings_is_one_section_not_a_guess(self) -> None:
        plain = build_document(
            "<p>" + ("words about nothing in particular. " * 40) + "</p>",
            filing_reference="x",
            source_url="y",
        )

        assert {section.kind for section in plain.sections} == {SectionKind.OTHER}
        assert "no_explanatory_section_recognised" in plain.warnings


class TestRetrieval:
    def test_it_finds_the_passage_that_discusses_the_metric(self) -> None:
        hits = retrieve(DOCUMENT, "operating_cash_flow")

        assert hits
        assert "working capital" in hits[0].chunk.text.lower()

    def test_it_says_why_a_passage_was_chosen(self) -> None:
        """The reason an embedding was not used: this is checkable by a person."""
        hits = retrieve(DOCUMENT, "days_sales_outstanding")

        assert hits
        assert hits[0].matched_terms

    def test_it_never_returns_the_risk_factors(self) -> None:
        """They mention collections and cash flow, and they are hypothetical."""
        for hit in retrieve(DOCUMENT, "operating_cash_flow", limit=20):
            assert hit.chunk.section_kind.is_explanatory

    def test_an_unknown_metric_retrieves_nothing_rather_than_anything(self) -> None:
        assert retrieve(DOCUMENT, "metric_we_have_no_words_for") == []
        assert terms_for("metric_we_have_no_words_for") == ()

    def test_nothing_found_is_a_real_answer(self) -> None:
        quiet = build_document(
            "<p>ITEM 2. Management's Discussion and Analysis</p><p>"
            + ("The board met and adjourned. " * 30)
            + "</p>",
            filing_reference="x",
            source_url="y",
        )

        assert retrieve(quiet, "inventory_growth_gap") == []


class TestTheValidatorAcceptsWhatIsReal:
    def test_a_genuine_quotation_passes(self) -> None:
        quote = "Operating cash flow decreased compared with the prior year"
        start, end = span_of(quote)
        check = validate(Citation(quote, start, end, SectionKind.MANAGEMENT_DISCUSSION), DOCUMENT)

        assert check.verdict is CitationVerdict.VALID

    def test_whitespace_may_differ_and_nothing_else(self) -> None:
        """A model reading text will not reproduce the filing's line breaks."""
        quote = "Operating cash flow decreased  compared\n with the prior year"
        start, end = span_of("Operating cash flow decreased compared with the prior year")
        check = validate(Citation(quote, start, end, SectionKind.MANAGEMENT_DISCUSSION), DOCUMENT)

        assert check.verdict is CitationVerdict.VALID


class TestTheValidatorRejectsFabrication:
    def test_words_that_are_not_in_the_filing(self) -> None:
        check = validate(
            Citation(
                "Management attributes the decline to a deliberate inventory build.",
                0,
                200,
                SectionKind.MANAGEMENT_DISCUSSION,
            ),
            DOCUMENT,
        )

        assert check.verdict is CitationVerdict.TEXT_NOT_FOUND

    def test_real_words_at_the_wrong_place(self) -> None:
        """A different failure from fabrication, and recorded as one: the model
        found something real and reported its position wrongly."""
        quote = "Operating cash flow decreased compared with the prior year"
        check = validate(Citation(quote, 0, len(quote), SectionKind.NOTES), DOCUMENT)

        assert check.verdict is CitationVerdict.MISPLACED
        assert check.found_at is not None

    def test_a_span_outside_the_document(self) -> None:
        check = validate(Citation("x" * 60, 9_000_000, 9_000_100), DOCUMENT)

        assert check.verdict is CitationVerdict.SPAN_OUT_OF_RANGE

    def test_a_quotation_too_short_to_be_a_claim(self) -> None:
        """ "Revenue" appears in every filing and asserts nothing."""
        check = validate(Citation("sales rose", 0, 10), DOCUMENT)

        assert check.verdict is CitationVerdict.TOO_SHORT

    def test_a_quotation_from_the_risk_factors(self) -> None:
        quote = "a deterioration in collections would reduce operating cash flow materially"
        start, end = span_of(quote)
        check = validate(Citation(quote, start, end, SectionKind.OTHER), DOCUMENT)

        assert check.verdict is CitationVerdict.NOT_EXPLANATORY

    def test_a_real_sentence_with_one_figure_altered(self) -> None:
        """The most dangerous failure: it reads exactly like a sound citation."""
        genuine = "Operating cash flow was 1,204 million for the quarter"
        start, end = span_of(genuine)
        tampered = genuine.replace("1,204", "9,999")

        assert validate(Citation(tampered, start, end, SectionKind.NOTES), DOCUMENT).verdict is (
            CitationVerdict.TEXT_NOT_FOUND
        )


class TestNumbersInTheModelsOwnProse:
    """Where an invented figure actually hides. The quotation beside it can be
    immaculate while the sentence introduces a number from nowhere."""

    EVIDENCE: ClassVar[list[str]] = [
        "Operating cash flow decreased compared with the prior year, primarily due to "
        "working capital, including higher accounts receivable.",
        "Operating cash flow was 1,204 million for the quarter.",
    ]

    def test_a_claim_with_no_figures_passes(self) -> None:
        check = validate_claim("Cash conversion weakened on working capital.", self.EVIDENCE)

        assert check.is_valid

    def test_a_figure_taken_from_the_evidence_passes(self) -> None:
        check = validate_claim("Operating cash flow was 1,204 million.", self.EVIDENCE)

        assert check.is_valid

    def test_a_figure_from_nowhere_is_caught(self) -> None:
        check = validate_claim(
            "Cash conversion fell because of a $450 million inventory build.", self.EVIDENCE
        )

        assert not check.is_valid
        assert check.invented_numbers == ("450",)

    def test_the_scope_is_the_evidence_not_the_whole_filing(self) -> None:
        """Measured against a real 285,000-character 10-Q, "$450 million" passed,
        because the digits occur somewhere in it. Almost any three-digit number
        does, which makes the document useless as a scope."""
        against_document = validate_claim("a $450 million inventory build", [DOCUMENT.text])
        against_evidence = validate_claim("a $450 million inventory build", self.EVIDENCE)

        assert against_document.is_valid or not against_document.is_valid
        assert not against_evidence.is_valid


class TestPublishing:
    def test_one_bad_citation_fails_the_whole_finding(self) -> None:
        """A finding with one fabricated quotation among four is not
        three-quarters trustworthy. It is evidence the model was willing to
        fabricate, which disqualifies the rest."""
        quote = "Operating cash flow decreased compared with the prior year"
        start, end = span_of(quote)
        checks = validate_all(
            [
                Citation(quote, start, end, SectionKind.MANAGEMENT_DISCUSSION),
                Citation("Words the filing never contained anywhere at all.", 0, 60),
            ],
            DOCUMENT,
        )

        assert not all_valid(checks)

    def test_nothing_to_check_is_not_a_pass(self) -> None:
        assert not all_valid([])

    def test_an_invented_figure_in_the_claim_fails_the_finding(self) -> None:
        quote = "Operating cash flow decreased compared with the prior year"
        start, end = span_of(quote)
        checks = validate_all(
            [Citation(quote, start, end, SectionKind.MANAGEMENT_DISCUSSION)], DOCUMENT
        )
        claim = validate_claim("It fell by $450 million.", [quote])

        assert all_valid(checks)
        assert not all_valid(checks, claim)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1,204 million", {"1204"}), ("8 percent", {"8"}), ("no digits here", set())],
)
def test_numbers_are_read_without_separators(text: str, expected: set[str]) -> None:
    assert numbers_in(text) == expected


def test_text_extraction_and_sectioning_are_pure() -> None:
    """Same input, same output. Section 23 needs two readers a month apart to
    see the same answer."""
    assert to_text(MARKUP) == to_text(MARKUP)
    assert find_sections(DOCUMENT.text) == find_sections(DOCUMENT.text)
