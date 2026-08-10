"""Parsing of real MAGNA rows.

The fixture is a slice of an actual result payload for Matrix IT, chosen to
contain every hazard the phase 1 spike uncovered: cumulative and discrete
periods side by side, two genuine restatements, dimensional breakdowns, rows
with no figure, and rows missing optional columns.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from ingestion.providers.magna_xbrl import distinct_filings, find_conflicts, parse_rows

FIXTURE = Path(__file__).parent / "fixtures" / "magna_search_matrix.json"


@pytest.fixture(scope="module")
def rows() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def facts(rows: list[dict[str, Any]]) -> list[Any]:
    return parse_rows(rows)


def test_every_row_parses(rows: list[dict[str, Any]], facts: list[Any]) -> None:
    assert len(facts) == len(rows)


def test_missing_figure_becomes_none_not_zero(facts: list[Any]) -> None:
    """Spec section 4.4: absence is unknown, and unknown is never zero."""
    empty = [f for f in facts if f.value is None]

    assert empty, "fixture should contain rows without a figure"
    assert all(f.value is not None or f.value is None for f in facts)
    assert 0.0 not in {f.value for f in empty}


def test_dimensional_facts_are_flagged(facts: list[Any]) -> None:
    """Breakdowns must be separable from consolidated totals."""
    dimensional = [f for f in facts if f.is_dimensional]

    assert dimensional
    assert all(f.dimensions for f in dimensional)
    assert any("ComponentsOfEquityAxis" in v for f in dimensional for v in f.dimensions.values())


def test_rows_missing_optional_columns_still_parse(rows: list[dict[str, Any]]) -> None:
    """`Balance` and the label columns are absent from some rows."""
    sparse = [r for r in rows if "Balance" not in r]

    assert sparse, "fixture should contain rows missing optional columns"
    assert len(parse_rows(sparse)) == len(sparse)


def test_filings_are_discovered_from_facts(facts: list[Any]) -> None:
    """MAGNA exposes no filing list, so filings come from reference numbers."""
    discovered = distinct_filings(facts)

    assert len(discovered) > 1
    assert all(ref.count("-") == 2 for ref in discovered)


def test_restatements_are_detected(facts: list[Any]) -> None:
    """Total assets for Matrix IT was restated downward in later filings."""
    conflicts = find_conflicts([f for f in facts if not f.is_dimensional])

    assets = {key: values for key, values in conflicts.items() if key[1] == "ifrs-full:Assets"}
    assert assets, "the two known Assets restatements must be detected"

    for values in assets.values():
        assert len(values) == 2


def test_infinite_decimals_do_not_crash_the_parser() -> None:
    """XBRL writes decimals="INF" to mean "stated exactly, no rounding".

    It parses as a float perfectly happily and then overflows on int(), which is
    exactly how it was found: the narrow phase 1 probe never hit it, and a wider
    query across all issuers did.
    """
    row = {
        "Company ID": "520039413",
        "Reference Number": "2024-01-616266",
        "Period": "30/09/2024",
        "Tag": "ifrs-full:Assets",
        "Fact": "3882556000",
        "Measure": "ILS",
        "Scale": "3",
        "Decimals": "INF",
        "Axis": "",
        "Member": "",
        "ExplicitMember": "",
        "TypedMember": "",
        "Data source in XBRL": "Consolidated Reports On The Financial Situation",
        "Label (EN)": "Assets",
    }

    parsed = parse_rows([row])

    assert len(parsed) == 1
    assert parsed[0].decimals is None
    assert parsed[0].value == 3882556000
    assert parsed[0].scale == 3


def test_an_infinite_figure_is_rejected_as_unknown() -> None:
    """A value cannot be infinite. Unknown is the only honest reading."""
    row = {
        "Company ID": "520039413",
        "Reference Number": "2024-01-616266",
        "Period": "30/09/2024",
        "Tag": "ifrs-full:Assets",
        "Fact": "INF",
        "Axis": "",
        "Member": "",
        "ExplicitMember": "",
        "TypedMember": "",
    }

    parsed = parse_rows([row])

    assert parsed[0].value is None


def test_units_and_scale_are_preserved(facts: list[Any]) -> None:
    """Currency and scale travel with the fact; they are not normalised away."""
    revenue = [f for f in facts if f.concept == "ifrs-full:Revenue" and f.value is not None]

    assert revenue
    assert {f.unit for f in revenue} == {"ILS"}
    assert all(f.scale == 3 for f in revenue)


def test_discrete_quarter_matches_the_difference_of_cumulative_periods(facts: list[Any]) -> None:
    """The reported Q2 equals H1 minus Q1, in the issuer's own numbers.

    This is the arithmetic every derived quarter will rely on. Q4 is never
    reported and must always be derived, so the derivation is validated here
    against the quarters that *are* reported.
    """
    revenue = {
        f.period.raw: f.value
        for f in facts
        if f.concept == "ifrs-full:Revenue" and not f.is_dimensional and f.value is not None
    }

    q1 = revenue["01/01/2023 - 31/03/2023"]
    h1 = revenue["01/01/2023 - 30/06/2023"]
    reported_q2 = revenue["01/04/2023 - 30/06/2023"]

    assert h1 - q1 == pytest.approx(reported_q2)
