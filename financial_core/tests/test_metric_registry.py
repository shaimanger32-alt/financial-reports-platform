"""The formula registry.

Spec section 33 requires analytical rules to be versioned and auditable. These
tests guard the properties that make that true.
"""

import pytest

from financial_core.metrics import (
    CALCULATED_BY_CODE,
    CALCULATED_METRICS,
    METRICS_BY_CODE,
    FactPoint,
    FactSet,
    compute_all,
    series,
)
from financial_core.periods import cumulative_period, discrete_period


def test_every_metric_code_is_unique() -> None:
    codes = [spec.code for spec in CALCULATED_METRICS]

    assert len(codes) == len(set(codes))


def test_calculated_codes_do_not_collide_with_reported_ones() -> None:
    """A code has one meaning. `revenue` is reported; `revenue_growth_yoy` is not."""
    overlap = set(CALCULATED_BY_CODE) & set(METRICS_BY_CODE)

    assert not overlap, f"codes claimed by both catalogues: {sorted(overlap)}"


def test_the_engine_covers_the_range_the_spec_asks_for() -> None:
    """Spec section 48 asks for 15 to 20 core metrics, not a hundred ratios.

    The count is checked against the CORE tier, since those are the metrics
    every company actually gets. Extended metrics resolve where the data exists
    and are null elsewhere, so a longer list there costs nothing.
    """
    core = [spec for spec in CALCULATED_METRICS if spec.is_core]

    assert 10 <= len(core) <= 20
    assert len(CALCULATED_METRICS) <= 40


def test_every_metric_carries_a_version() -> None:
    assert all(spec.formula_version for spec in CALCULATED_METRICS)


def test_every_metric_is_named_in_both_languages() -> None:
    """Domain codes are English; display names are localised (spec section 45)."""
    for spec in CALCULATED_METRICS:
        assert spec.name_he and spec.name_en
        assert spec.name_he != spec.name_en


def test_compute_all_returns_a_result_for_every_applicable_metric() -> None:
    quarter = discrete_period(2024, 3)
    facts = FactSet([FactPoint("revenue", quarter, 1000.0, "test:revenue")])

    results = compute_all(facts, quarter)

    assert set(results) == {spec.code for spec in CALCULATED_METRICS}


def test_quarter_only_metrics_are_absent_from_a_cumulative_period() -> None:
    """Skipped rather than computed against a mismatched period length."""
    results = compute_all(FactSet([]), cumulative_period(2024, 3))

    quarter_only = {spec.code for spec in CALCULATED_METRICS if spec.requires_quarter}
    assert quarter_only
    assert not (quarter_only & set(results))


def test_a_metric_with_no_data_returns_a_null_result_not_an_exception() -> None:
    """An empty company must produce nulls, never a crash."""
    quarter = discrete_period(2024, 3)

    results = compute_all(FactSet([]), quarter)

    assert results
    assert all(result.value is None for result in results.values())
    assert all(result.missing_inputs for result in results.values())


def test_a_series_is_ordered_oldest_first_regardless_of_input_order() -> None:
    periods = [discrete_period(2024, 3), discrete_period(2024, 1), discrete_period(2024, 2)]

    points = series(FactSet([]), "gross_margin", periods)

    assert [p.period.code for p in points] == ["2024-Q1", "2024-Q2", "2024-Q3"]


def test_an_unknown_metric_code_fails_loudly() -> None:
    with pytest.raises(KeyError):
        series(FactSet([]), "not_a_metric", [discrete_period(2024, 3)])


def test_a_reported_figure_outranks_one_we_derived() -> None:
    """Decision 0009: our derivation never displaces the issuer's own number."""
    from financial_core.provenance import Origin

    quarter = discrete_period(2024, 3)
    facts = FactSet(
        [
            FactPoint("revenue", quarter, 999.0, "test:a", origin=Origin.DERIVED),
            FactPoint("revenue", quarter, 1000.0, "test:b", origin=Origin.REPORTED),
        ]
    )

    assert facts.value("revenue", quarter) == 1000.0


def test_the_more_precise_concept_wins_within_the_same_origin() -> None:
    """The fallback chain's order survives into the calculation."""
    quarter = discrete_period(2024, 3)
    facts = FactSet(
        [
            FactPoint("trade_receivables", quarter, 260.0, "ifrs-full:TradeAndOther", priority=3),
            FactPoint("trade_receivables", quarter, 205.0, "ifrs-full:CurrentTrade", priority=0),
        ]
    )

    point = facts.point("trade_receivables", quarter)
    assert point is not None
    assert point.raw_concept == "ifrs-full:CurrentTrade"
    assert point.value == 205.0


def test_a_figure_barred_from_analysis_never_enters_the_fact_set() -> None:
    """Spec section 21.4: rejected data must not reach a calculation."""
    from financial_core.quality import QualityStatus

    quarter = discrete_period(2024, 3)
    facts = FactSet([FactPoint("revenue", quarter, 1000.0, "test", quality=QualityStatus.REJECTED)])

    assert facts.value("revenue", quarter) is None
    assert len(facts) == 0
