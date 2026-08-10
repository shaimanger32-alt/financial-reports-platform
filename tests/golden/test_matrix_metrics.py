"""Golden metrics: real filings in, verified numbers out.

Spec section 48 requires the figures to be checked by hand against a real report
before the engine is trusted. These expectations were computed from Matrix IT's
own published revenue, cost of sales, gross profit and operating profit, and are
reproduced here so that any change to a formula has to reproduce them too.

Matrix IT, Q3 2024 versus Q3 2023, from the issuer's standalone quarterly
figures:

    Revenue          1,418,810,000    vs  1,333,520,000   -> +6.40%
    Gross profit       205,036,000    vs    187,053,000
    Gross margin            14.45%    vs         14.03%   -> +0.42pp
"""

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from database.repository import find_company, load_fact_set
from financial_core.metrics import FactSet, MetricWarning, compute_all, series
from financial_core.metrics import formulas as f
from financial_core.periods import cumulative_period, discrete_period
from ingestion.pipelines.magna import ingest_batch
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

Q3_2024 = discrete_period(2024, 3)
Q3_2023 = discrete_period(2023, 3)


@pytest.fixture
def facts(session: Session) -> FactSet:
    payload = FIXTURE.read_bytes()
    batch = FactBatch(
        facts=parse_rows(json.loads(payload)),
        raw_payload=payload,
        content_hash="golden",
        retrieved_at="2026-08-09T00:00:00Z",
        source_reference="golden:magna_matrix",
    )
    seed_reference_data(session)
    ingest_batch(session, MATRIX, batch)

    company = find_company(session, "520039413")
    assert company is not None
    return load_fact_set(session, company.id)


def test_the_fact_set_is_populated(facts: FactSet) -> None:
    assert len(facts) > 100
    assert "revenue" in facts.metrics()


def test_revenue_reaches_the_engine_under_its_canonical_name(facts: FactSet) -> None:
    """The engine asks for `revenue`, not for an XBRL tag."""
    assert facts.value("revenue", Q3_2024) == pytest.approx(1_418_810_000)
    assert facts.value("revenue", Q3_2023) == pytest.approx(1_333_520_000)


def test_revenue_growth_matches_the_hand_calculation(facts: FactSet) -> None:
    result = f.revenue_growth_yoy(facts, Q3_2024)

    assert result.value == pytest.approx(0.0639, abs=0.0001)
    assert not result.warnings


@pytest.mark.parametrize(
    ("period", "expected"),
    [(Q3_2023, 0.1403), (Q3_2024, 0.1445)],
)
def test_gross_margin_matches_the_hand_calculation(
    facts: FactSet, period: object, expected: float
) -> None:
    result = f.gross_margin(facts, period)  # type: ignore[arg-type]

    assert result.value == pytest.approx(expected, abs=0.0001)


def test_gross_margin_movement_is_reported_in_percentage_points(facts: FactSet) -> None:
    result = f.gross_margin_change_pp(facts, Q3_2024)

    assert result.value == pytest.approx(0.42, abs=0.01)


def test_operating_margin_matches_the_hand_calculation(facts: FactSet) -> None:
    assert f.operating_margin(facts, Q3_2024).value == pytest.approx(0.0762, abs=0.0001)
    assert f.operating_margin(facts, Q3_2023).value == pytest.approx(0.0699, abs=0.0001)


def test_a_derived_q4_feeds_the_metrics(facts: FactSet) -> None:
    """Q4 is never reported, so without the derivation the fourth quarter of
    every year would simply be absent from the series."""
    assert facts.value("revenue", discrete_period(2023, 4)) == pytest.approx(1_320_690_000)


def test_margins_work_on_cumulative_periods_too(facts: FactSet) -> None:
    """A year-to-date margin is legitimate; it is mixing kinds that is not."""
    annual = cumulative_period(2023, 4)

    assert f.gross_margin(facts, annual).is_available


def test_metrics_needing_a_quarter_are_skipped_on_cumulative_periods(facts: FactSet) -> None:
    """Rather than computed against a mismatched period length."""
    quarterly = compute_all(facts, Q3_2024)
    annual = compute_all(facts, cumulative_period(2023, 4))

    assert "days_sales_outstanding" in quarterly
    assert "days_sales_outstanding" not in annual


def test_days_sales_outstanding_is_computable_for_matrix(facts: FactSet) -> None:
    """Matrix tags trade receivables, so the working capital metrics resolve."""
    result = f.days_sales_outstanding(facts, Q3_2024)

    assert result.is_available
    assert 0 < (result.value or 0) < 365


def test_metrics_that_depend_on_untagged_data_are_null_not_zero(facts: FactSet) -> None:
    """Debt is thinly tagged across this market. Null is the honest answer."""
    result = f.net_debt(facts, Q3_2024)

    assert result.value is None
    assert MetricWarning.MISSING_INPUT in result.warnings


def test_a_historical_series_comes_back_in_order(facts: FactSet) -> None:
    periods = [discrete_period(2023, q) for q in (1, 2, 3, 4)]

    points = series(facts, "gross_margin", periods)

    assert [p.period.code for p in points] == ["2023-Q1", "2023-Q2", "2023-Q3", "2023-Q4"]
    assert all(p.is_available for p in points)
    assert all(p.formula_version == "v1" for p in points)


def test_every_result_carries_its_formula_version(facts: FactSet) -> None:
    """Spec section 33: a figure must stay explainable by the rule that made it."""
    results = compute_all(facts, Q3_2024)

    assert results
    assert all(result.formula_version for result in results.values())
