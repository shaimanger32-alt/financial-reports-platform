"""Deriving discrete quarters from cumulative American filings.

Israeli issuers report the second and third quarters discretely, so only the
fourth had to be derived. **American filers do not.** Apple's cash flow
statement carries 56 year-to-date windows against 27 discrete ones, and the 27
are all first quarters — which are cumulative and discrete at once. So
`Qn = YTD(n) - YTD(n-1)` is needed for every quarter here, not just the last.

That is not a new engine. `derive_quarter` already differences cumulative
figures for any quarter; what changed is that the American path has to use it
everywhere, and that every metric resting on quarterly cash flow was null until
it did.

The check below is the same one that validated the Israeli Q4 derivation:
revenue is reported *both* cumulatively and discretely, so the derivation can be
compared against the figure the company itself published.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from financial_core.periods import classify_in, derive_quarter, discrete_period
from ingestion.providers.sec_edgar import learn_fiscal_calendar

FIXTURE = Path(__file__).parent / "fixtures" / "apple_companyfacts.json"
DOCUMENT = json.loads(FIXTURE.read_text())
CALENDAR = learn_fiscal_calendar(DOCUMENT)

REVENUE = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _by_period(concept: str) -> dict[str, float]:
    """Every classified figure for one concept, keyed by period code."""
    values: dict[str, float] = {}
    for unit in DOCUMENT["facts"]["us-gaap"][concept]["units"].values():
        for row in unit:
            period = classify_in(
                date.fromisoformat(row["start"]) if row.get("start") else None,
                date.fromisoformat(row["end"]),
                CALENDAR,
            )
            if period is not None and isinstance(row.get("val"), int | float):
                values.setdefault(period.code, float(row["val"]))
    return values


REVENUE_BY_PERIOD = _by_period(REVENUE)


@pytest.mark.parametrize(
    ("fiscal_year", "quarter"),
    [(year, quarter) for year in (2023, 2024, 2025) for quarter in (1, 2, 3)],
)
def test_the_derived_quarter_matches_the_one_apple_reported(fiscal_year: int, quarter: int) -> None:
    """Nine quarters across three fiscal years, two of them 52-week and one 53."""
    derived = derive_quarter(
        fiscal_year, quarter, lambda period: REVENUE_BY_PERIOD.get(period.code)
    )
    reported = REVENUE_BY_PERIOD.get(discrete_period(fiscal_year, quarter).code)

    assert derived is not None, "the cumulative inputs should be present"
    assert reported is not None, "Apple reports this quarter discretely"
    assert derived.value == pytest.approx(reported)


def test_the_derivation_records_what_it_was_built_from() -> None:
    """Spec section 4.2: a derived figure has to be traceable to its inputs."""
    derived = derive_quarter(2025, 3, lambda period: REVENUE_BY_PERIOD.get(period.code))

    assert derived is not None
    assert len(derived.inputs) == 2
    assert "-" in derived.formula


def test_a_missing_cumulative_input_yields_nothing() -> None:
    """Unknown is never zero, and no partial arithmetic is attempted."""
    assert derive_quarter(2025, 3, lambda period: None) is None


def test_the_first_quarter_needs_no_differencing() -> None:
    """Q1 is cumulative and discrete at once, in both markets."""
    derived = derive_quarter(2025, 1, lambda period: REVENUE_BY_PERIOD.get(period.code))

    assert derived is not None
    assert len(derived.inputs) == 1


def test_american_cash_flow_really_is_cumulative_only() -> None:
    """The finding that made this necessary. If a future filing started
    reporting discrete quarters, this test says so rather than leaving the
    derivation running for no reason."""
    cash_flow = "NetCashProvidedByUsedInOperatingActivities"
    if cash_flow not in DOCUMENT["facts"]["us-gaap"]:
        pytest.skip("cash flow is not in the trimmed fixture")

    discrete = [
        code
        for code in _by_period(cash_flow)
        if "-Q" in code and "YTD" not in code and not code.endswith("-AT")
    ]

    # Every discrete cash flow period Apple files is a first quarter, which is
    # cumulative and discrete at the same time.
    assert all(code.endswith("-Q1") for code in discrete)
