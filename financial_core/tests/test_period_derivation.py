"""Deriving discrete quarters, and reconciling them against reported ones.

The golden case uses Matrix IT's actual reported revenue, taken from the phase 1
spike. Q2 and Q3 are checked against the issuer's own standalone figures, which
is the only way to validate the arithmetic that Q4 depends on -- Q4 is never
reported by anyone.
"""

import pytest

from financial_core.periods import (
    DerivationNotApplicableError,
    DurationKind,
    FiscalPeriod,
    PeriodKind,
    cumulative_period,
    derive_quarter,
    derive_quarter_for_flow,
    discrete_period,
    reconcile,
    rounding_tolerance,
    values_agree,
)

# ifrs-full:Revenue, MATRIX IT LTD (520039413), whole ILS.
MATRIX_CUMULATIVE_REVENUE: dict[str, float] = {
    "2023-Q1": 1_291_153_000,
    "2023-YTD-Q2": 2_577_895_000,
    "2023-YTD-Q3": 3_911_415_000,
    "2023-FY": 5_232_105_000,
    "2024-Q1": 1_453_713_000,
    "2024-YTD-Q2": 2_786_445_000,
    "2024-YTD-Q3": 4_205_255_000,
    "2024-FY": 5_579_538_000,
}

# The same issuer's standalone quarters, as reported.
MATRIX_REPORTED_QUARTERS: dict[str, float] = {
    "2023-Q2": 1_286_742_000,
    "2023-Q3": 1_333_520_000,
    "2024-Q2": 1_332_732_000,
    "2024-Q3": 1_418_810_000,
}


def matrix_lookup(period: FiscalPeriod) -> float | None:
    return MATRIX_CUMULATIVE_REVENUE.get(period.code)


def empty_lookup(period: FiscalPeriod) -> float | None:
    return None


@pytest.mark.parametrize(("year", "quarter"), [(2023, 2), (2023, 3), (2024, 2), (2024, 3)])
def test_derived_quarter_matches_the_issuers_own_figure(year: int, quarter: int) -> None:
    """The derivation reproduces what the company itself reported."""
    derivation = derive_quarter(year, quarter, matrix_lookup)

    assert derivation is not None
    expected = MATRIX_REPORTED_QUARTERS[f"{year}-Q{quarter}"]
    assert derivation.value == pytest.approx(expected)


@pytest.mark.parametrize(("year", "expected"), [(2023, 1_320_690_000), (2024, 1_374_283_000)])
def test_q4_is_derived_because_it_is_never_reported(year: int, expected: float) -> None:
    derivation = derive_quarter(year, 4, matrix_lookup)

    assert derivation is not None
    assert derivation.value == pytest.approx(expected)
    assert derivation.formula == f"Q4 = {year}-FY - {year}-YTD-Q3"


def test_q1_is_an_identity_not_a_subtraction() -> None:
    derivation = derive_quarter(2023, 1, matrix_lookup)

    assert derivation is not None
    assert derivation.is_identity
    assert derivation.value == pytest.approx(1_291_153_000)
    assert len(derivation.inputs) == 1


def test_derivation_records_the_facts_it_came_from() -> None:
    """Spec section 4.2: every derived figure traces back to reported ones."""
    derivation = derive_quarter(2024, 3, matrix_lookup)

    assert derivation is not None
    codes = [period.code for period, _ in derivation.inputs]
    assert codes == ["2024-YTD-Q3", "2024-YTD-Q2"]
    assert [value for _, value in derivation.inputs] == [4_205_255_000, 2_786_445_000]


def test_a_missing_input_yields_nothing_rather_than_a_partial_answer() -> None:
    """Unknown is unknown. It is never treated as zero (spec section 4.4)."""
    partial = {"2024-YTD-Q3": 4_205_255_000.0}

    def lookup(period: FiscalPeriod) -> float | None:
        return partial.get(period.code)

    assert derive_quarter(2024, 3, lookup) is None
    assert derive_quarter(2024, 4, lookup) is None


def test_no_data_at_all_yields_nothing() -> None:
    assert derive_quarter(2024, 2, empty_lookup) is None


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_invalid_quarter_is_rejected(quarter: int) -> None:
    with pytest.raises(ValueError, match="fiscal quarter out of range"):
        derive_quarter(2024, quarter, matrix_lookup)


def test_balances_cannot_be_differenced_into_quarters() -> None:
    """Subtracting two balance dates gives a movement, not a quarterly flow."""
    with pytest.raises(DerivationNotApplicableError):
        derive_quarter_for_flow(PeriodKind.INSTANT, 2024, 2, matrix_lookup)


def test_flows_pass_the_guard() -> None:
    derivation = derive_quarter_for_flow(PeriodKind.DURATION, 2024, 2, matrix_lookup)

    assert derivation is not None
    assert derivation.value == pytest.approx(1_332_732_000)


def test_cumulative_period_shapes() -> None:
    assert cumulative_period(2024, 1).duration_kind is DurationKind.QUARTER
    assert cumulative_period(2024, 2).duration_kind is DurationKind.YTD
    assert cumulative_period(2024, 3).duration_kind is DurationKind.YTD
    assert cumulative_period(2024, 4).duration_kind is DurationKind.ANNUAL


def test_discrete_period_is_always_a_quarter() -> None:
    for quarter in (1, 2, 3, 4):
        period = discrete_period(2024, quarter)
        assert period.duration_kind is DurationKind.QUARTER
        assert period.code == f"2024-Q{quarter}"


@pytest.mark.parametrize(("year", "quarter"), [(2023, 2), (2023, 3), (2024, 2), (2024, 3)])
def test_reconciliation_agrees_on_real_data(year: int, quarter: int) -> None:
    derivation = derive_quarter(year, quarter, matrix_lookup)
    assert derivation is not None

    result = reconcile(
        derivation.period,
        reported=MATRIX_REPORTED_QUARTERS[f"{year}-Q{quarter}"],
        derived=derivation.value,
    )

    assert result.agrees is True
    assert result.difference == pytest.approx(0.0)


def test_reconciliation_reports_a_disagreement_without_resolving_it() -> None:
    """Decision 0009: both figures survive, and the difference is visible."""
    period = discrete_period(2024, 2)

    result = reconcile(period, reported=1_332_732_000, derived=1_300_000_000)

    assert result.agrees is False
    assert result.reported == 1_332_732_000
    assert result.derived == 1_300_000_000
    assert result.difference == pytest.approx(32_732_000)


def test_reconciliation_concludes_nothing_when_a_side_is_missing() -> None:
    period = discrete_period(2024, 4)

    result = reconcile(period, reported=None, derived=1_374_283_000)

    assert result.agrees is None
    assert result.difference is None


def test_agreement_tolerates_float_noise_but_not_real_differences() -> None:
    assert values_agree(5_232_105_000.0, 5_232_105_000.0000001)
    assert not values_agree(5_232_105_000.0, 5_232_106_000.0)


def test_rounding_tolerance_follows_the_tagging_granularity() -> None:
    """A figure tagged to the nearest thousand carries thousand-scale rounding."""
    assert rounding_tolerance(-3) == 1_500.0
    assert rounding_tolerance(-6) == 1_500_000.0
    assert rounding_tolerance(0) == 1.0
    assert rounding_tolerance(None) == 1.0


def test_tagging_granularity_is_not_a_disagreement() -> None:
    """Matrix IT's Q2 2023 profit: 62,822,000 reported, 62,823,000 derived.

    Two cumulative figures rounded to the nearest thousand were subtracted, so a
    gap of one thousand is arithmetic, not error. Flagging it would raise a false
    alarm on a sound figure.
    """
    period = discrete_period(2023, 2)

    naive = reconcile(period, reported=62_822_000, derived=62_823_000)
    aware = reconcile(period, reported=62_822_000, derived=62_823_000, decimals=-3)

    assert naive.agrees is False
    assert aware.agrees is True


def test_a_real_disagreement_still_fails_at_thousand_granularity() -> None:
    period = discrete_period(2023, 2)

    result = reconcile(period, reported=62_822_000, derived=61_000_000, decimals=-3)

    assert result.agrees is False
