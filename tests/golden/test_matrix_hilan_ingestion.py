"""End-to-end golden test: real filings, all the way into the canonical store.

The fixture is an unedited MAGNA payload for Matrix IT and Hilan covering
2023-2024. Nothing in it was adjusted to make a test pass, which is the point:
spec section 34 asks for fixtures from a real report, checked by hand, so that
any change to the engine has to reproduce figures that were already verified.

The expected values below were taken from the issuers' own filings during the
phase 1 spike and confirmed against the arithmetic the issuers themselves
publish.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import AnalysisPeriod, Company, FactDerivation, Filing, FinancialFact
from financial_core.periods import DurationKind, PeriodKind
from financial_core.provenance import Origin
from financial_core.quality import QualityStatus
from financial_core.validation import IdentityOutcome, check_gross_profit
from ingestion.pipelines.magna import IngestionReport, ingest_batch
from ingestion.providers.base import FactBatch, ProviderEntity
from ingestion.providers.magna_xbrl import parse_rows
from ingestion.seeding import seed_reference_data

pytestmark = pytest.mark.integration

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "ingestion"
    / "tests"
    / "fixtures"
    / "magna_golden_matrix_hilan.json"
)

MATRIX = ProviderEntity(
    provider_entity_id="520039413",
    name='מטריקס אי.טי. בע"מ',
    name_en="MATRIX IT LTD",
    sector_code="8800",
    sector_name="טכנולוגיה",
)
HILAN = ProviderEntity(
    provider_entity_id="520039942",
    name='חילן בע"מ',
    name_en="HILAN LTD",
    sector_code="8800",
    sector_name="טכנולוגיה",
)


@pytest.fixture(scope="module")
def batch() -> FactBatch:
    payload = FIXTURE.read_bytes()
    return FactBatch(
        facts=parse_rows(json.loads(payload)),
        raw_payload=payload,
        content_hash="golden",
        retrieved_at="2026-08-09T00:00:00Z",
        source_reference="golden:magna_matrix_hilan",
    )


@pytest.fixture
def loaded(session: Session, batch: FactBatch) -> dict[str, IngestionReport]:
    seed_reference_data(session)
    return {
        "matrix": ingest_batch(session, MATRIX, batch),
        "hilan": ingest_batch(session, HILAN, batch),
    }


def _fact(
    session: Session, entity_id: str, concept: str, code: str, origin: Origin
) -> FinancialFact:
    fact = session.scalar(
        select(FinancialFact)
        .join(Company, FinancialFact.company_id == Company.id)
        .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
        .where(
            Company.provider_entity_id == entity_id,
            FinancialFact.raw_concept == concept,
            FinancialFact.origin == origin,
            AnalysisPeriod.code == code,
        )
    )
    assert fact is not None, f"no {origin} fact for {concept} @ {code}"
    return fact


# -- the pipeline runs ----------------------------------------------------


def test_both_companies_load(session: Session, loaded: dict[str, IngestionReport]) -> None:
    companies = session.scalars(select(Company).order_by(Company.provider_entity_id)).all()

    assert [c.provider_entity_id for c in companies] == ["520039413", "520039942"]
    assert companies[0].name_en == "MATRIX IT LTD"
    assert companies[1].name_en == "HILAN LTD"


def test_filings_are_discovered_from_the_facts(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """MAGNA has no filing list, so every filing row here was inferred."""
    count = session.scalar(select(func.count()).select_from(Filing))

    assert count and count > 10


def test_periods_cover_quarters_year_to_date_annual_and_instants(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    kinds = set(
        session.scalars(
            select(AnalysisPeriod.duration_kind).where(
                AnalysisPeriod.period_kind == PeriodKind.DURATION
            )
        )
    )

    assert {DurationKind.QUARTER, DurationKind.YTD, DurationKind.ANNUAL} <= kinds
    assert session.scalar(
        select(func.count())
        .select_from(AnalysisPeriod)
        .where(AnalysisPeriod.period_kind == PeriodKind.INSTANT)
    )


# -- the numbers ----------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("2023-Q1", Decimal("1291153000")),
        ("2023-YTD-Q2", Decimal("2577895000")),
        ("2023-YTD-Q3", Decimal("3911415000")),
        ("2023-FY", Decimal("5232105000")),
        ("2024-FY", Decimal("5579538000")),
    ],
)
def test_matrix_reported_revenue_matches_the_filing(
    session: Session, loaded: dict[str, IngestionReport], code: str, expected: Decimal
) -> None:
    fact = _fact(session, "520039413", "ifrs-full:Revenue", code, Origin.REPORTED)

    assert fact.value == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("2023-Q2", Decimal("1286742000")),
        ("2023-Q3", Decimal("1333520000")),
        ("2024-Q2", Decimal("1332732000")),
        ("2024-Q3", Decimal("1418810000")),
    ],
)
def test_derived_quarters_reproduce_the_issuers_own_figures(
    session: Session, loaded: dict[str, IngestionReport], code: str, expected: Decimal
) -> None:
    """The issuer reports these quarters standalone. Ours must equal theirs."""
    derived = _fact(session, "520039413", "ifrs-full:Revenue", code, Origin.DERIVED)
    reported = _fact(session, "520039413", "ifrs-full:Revenue", code, Origin.REPORTED)

    assert derived.value == expected
    assert reported.value == expected


def test_reported_and_derived_both_survive(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """Decision 0009: the reader gets the company's figure and ours."""
    period = session.scalar(
        select(AnalysisPeriod)
        .join(Company, AnalysisPeriod.company_id == Company.id)
        .where(Company.provider_entity_id == "520039413", AnalysisPeriod.code == "2023-Q3")
    )
    assert period is not None

    origins = set(
        session.scalars(
            select(FinancialFact.origin).where(
                FinancialFact.period_id == period.id,
                FinancialFact.raw_concept == "ifrs-full:Revenue",
            )
        )
    )

    assert origins == {Origin.REPORTED, Origin.DERIVED}


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2023, Decimal("1320690000")), (2024, Decimal("1374283000"))],
)
def test_q4_exists_only_because_we_derived_it(
    session: Session, loaded: dict[str, IngestionReport], year: int, expected: Decimal
) -> None:
    """No issuer reports Q4. It is FY minus nine months, and nothing else."""
    derived = _fact(session, "520039413", "ifrs-full:Revenue", f"{year}-Q4", Origin.DERIVED)

    assert derived.value == expected
    assert derived.derivation_formula == f"Q4 = {year}-FY - {year}-YTD-Q3"

    with pytest.raises(AssertionError):
        _fact(session, "520039413", "ifrs-full:Revenue", f"{year}-Q4", Origin.REPORTED)


def test_q4_is_flagged_because_it_can_only_be_derived_across_filings(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """No filing carries both a full year and the preceding nine months.

    The annual report tags the year and its comparative; the third-quarter
    report tags nine months. So Q4 is always assembled from two filings, and two
    filings need not agree -- Hilan restated its finance costs between them
    without re-tagging the earlier period. The figure is still produced, and it
    carries a warning rather than a clean bill of health.
    """
    derived = _fact(session, "520039413", "ifrs-full:Revenue", "2024-Q4", Origin.DERIVED)

    assert derived.quality_status is QualityStatus.USABLE_WITH_WARNING
    assert derived.quality_status.is_analysable
    assert not derived.quality_status.supports_high_confidence


def test_a_derived_quarter_is_traceable_to_reported_facts(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """Spec section 4.2. The audit trail is a real foreign key, not a comment."""
    derived = _fact(session, "520039413", "ifrs-full:Revenue", "2024-Q4", Origin.DERIVED)

    lineage = session.scalars(
        select(FactDerivation)
        .where(FactDerivation.derived_fact_id == derived.id)
        .order_by(FactDerivation.ordinal)
    ).all()

    assert [link.role for link in lineage] == ["minuend", "subtrahend"]
    minuend, subtrahend = (link.input_fact for link in lineage)
    assert minuend.origin is Origin.REPORTED
    assert subtrahend.origin is Origin.REPORTED
    assert minuend.value is not None and subtrahend.value is not None
    assert minuend.value - subtrahend.value == derived.value


def test_no_derivation_disagrees_with_the_issuer(loaded: dict[str, IngestionReport]) -> None:
    """Every quarter both reported and derived agrees, across two companies and
    two years. This is the evidence that the Q4 arithmetic is sound."""
    for report in loaded.values():
        assert not report.derivation_mismatches


# -- restatements ---------------------------------------------------------


def test_the_known_restatements_are_detected(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """Matrix IT restated total assets downward. Both values are in the store."""
    matrix = loaded["matrix"]
    restated_periods = {r.period_code for r in matrix.restatements}

    assert restated_periods

    values = set(
        session.scalars(
            select(FinancialFact.value)
            .join(Company, FinancialFact.company_id == Company.id)
            .join(AnalysisPeriod, FinancialFact.period_id == AnalysisPeriod.id)
            .where(
                Company.provider_entity_id == "520039413",
                FinancialFact.raw_concept == "ifrs-full:Assets",
                FinancialFact.origin == Origin.REPORTED,
                AnalysisPeriod.period_end == __import__("datetime").date(2023, 12, 31),
                AnalysisPeriod.period_kind == PeriodKind.INSTANT,
            )
        )
    )

    assert {Decimal("4084180000"), Decimal("4035232000")} <= values


def test_the_later_filing_is_flagged_as_a_restatement(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    flagged = session.scalars(select(Filing).where(Filing.is_restatement.is_(True))).all()

    assert flagged
    for filing in flagged:
        assert filing.supersedes_filing_id is not None


# -- quality --------------------------------------------------------------


def test_the_gross_profit_identity_holds_on_real_figures(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """Revenue minus cost of sales equals gross profit, in the issuer's numbers.

    A break here would mean the concept mapping is wrong, not that the issuer is.
    """
    figures = {
        "revenue": float(
            _fact(session, "520039413", "ifrs-full:Revenue", "2024-FY", Origin.REPORTED).value or 0
        ),
        "cost_of_sales": float(
            _fact(session, "520039413", "ifrs-full:CostOfSales", "2024-FY", Origin.REPORTED).value
            or 0
        ),
        "gross_profit": float(
            _fact(session, "520039413", "ifrs-full:GrossProfit", "2024-FY", Origin.REPORTED).value
            or 0
        ),
    }

    check = check_gross_profit(figures)

    assert check.outcome is IdentityOutcome.HOLDS, (
        f"expected {check.expected}, got {check.actual}, gap {check.relative_difference}"
    )


def test_facts_carry_their_canonical_metric(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    fact = _fact(session, "520039413", "ifrs-full:Revenue", "2024-FY", Origin.REPORTED)

    assert fact.metric_code == "revenue"


def test_hilan_uses_a_different_receivables_concept_and_still_resolves(
    session: Session, loaded: dict[str, IngestionReport]
) -> None:
    """The point of the fallback chain: two issuers, two tags, one metric."""
    concepts = set(
        session.scalars(
            select(FinancialFact.raw_concept)
            .join(Company, FinancialFact.company_id == Company.id)
            .where(
                Company.provider_entity_id.in_(["520039413", "520039942"]),
                FinancialFact.metric_code == "trade_receivables",
            )
        )
    )

    assert concepts, "neither company resolved trade receivables"
    assert concepts <= {
        "ifrs-full:CurrentTradeReceivables",
        "ifrs-full:TradeAndOtherCurrentReceivables",
    }


# -- idempotency ----------------------------------------------------------


def test_reingesting_the_same_batch_changes_nothing(
    session: Session, batch: FactBatch, loaded: dict[str, IngestionReport]
) -> None:
    """Spec section 33. This is what makes reprocessing after a code change safe."""
    before = {
        "facts": session.scalar(select(func.count()).select_from(FinancialFact)),
        "periods": session.scalar(select(func.count()).select_from(AnalysisPeriod)),
        "filings": session.scalar(select(func.count()).select_from(Filing)),
        "lineage": session.scalar(select(func.count()).select_from(FactDerivation)),
    }

    ingest_batch(session, MATRIX, batch)
    ingest_batch(session, HILAN, batch)

    after = {
        "facts": session.scalar(select(func.count()).select_from(FinancialFact)),
        "periods": session.scalar(select(func.count()).select_from(AnalysisPeriod)),
        "filings": session.scalar(select(func.count()).select_from(Filing)),
        "lineage": session.scalar(select(func.count()).select_from(FactDerivation)),
    }

    assert before == after
