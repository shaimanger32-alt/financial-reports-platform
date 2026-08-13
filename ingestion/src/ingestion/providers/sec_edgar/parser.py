"""Turning an SEC `companyfacts` payload into provider facts.

Pure: no network, no configuration, no clock. Everything here can be tested
against a saved payload, which is how the fiscal calendar logic gets exercised
against Apple's real nineteen years of filings rather than an invention.

The payload is shaped `facts -> taxonomy -> concept -> units -> [rows]`, and a
row looks like:

    {"start": "2025-09-28", "end": "2025-12-27", "val": 143756000000,
     "accn": "0000320193-26-000008", "fy": 2026, "fp": "Q1",
     "form": "10-Q", "filed": "2026-01-29"}

Two of those fields are traps.

`fy` and `fp` describe **the filing the row appeared in, not the period the row
measures.** Apple's fiscal 2023 revenue appears three times, tagged `fy=2023`,
`fy=2024` and `fy=2025`, because the later filings carry it as a comparative.
Reading `fp` as the period's own quarter would misfile two thirds of history.
Periods are therefore classified from their dates against the company's own
fiscal calendar, and `fp` is never trusted.

`filed`, by contrast, is a genuine publication date. MAGNA supplies none, which
forced decision 0009 to infer recency from a reference number. For American
filings there is nothing to infer.
"""

import json
from collections import defaultdict
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any, Final

from financial_core.periods import FiscalCalendar, FiscalYearWindow
from ingestion.providers.base import ProviderFact, ProviderPeriod

# A fiscal year is twelve months give or take. A 52-week year is 364 days and a
# 53-week year is 371; a calendar year is 365 or 366. Anything outside this band
# is a transition period or a stub, and is not a year we can reason about.
MIN_FISCAL_YEAR_DAYS: Final[int] = 350
MAX_FISCAL_YEAR_DAYS: Final[int] = 380

ANNUAL_FORMS: Final[frozenset[str]] = frozenset({"10-K", "10-K/A", "20-F", "40-F"})

# How far a fiscal year's label may sit from the calendar year it ends in.
#
# Zero for most filers, and one for a retailer whose year ends in January: Target
# calls the year ending 2026-01-31 "fiscal 2025". Anything further apart is not a
# label at all — it is a comparative carrying the *filing's* year, and trusting
# it put Apple's fiscal 2007 into the store as fiscal 2009, with four different
# years' revenue landing in one period.
MAX_LABEL_DRIFT: Final[int] = 1


def _rows(payload: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Every fact row, with the concept and unit it was filed under."""
    for taxonomy, concepts in payload.get("facts", {}).items():
        for concept, body in concepts.items():
            for unit, entries in body.get("units", {}).items():
                for entry in entries:
                    yield f"{taxonomy}:{concept}", unit, entry


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def learn_fiscal_calendar(payload: dict[str, Any]) -> FiscalCalendar:
    """Reconstruct the company's fiscal years from the windows it reported.

    A fiscal year is a roughly twelve-month window that an annual report tagged.
    Its label is the **lowest** `fy` any row gives it, because the first filing
    to carry a year is that year's own annual report; every later appearance is
    a comparative carrying the later filing's label.

    Returns an empty calendar when nothing qualifies. An empty calendar
    classifies nothing, which is the correct outcome for a company whose annual
    filings we do not hold — better than assuming December.
    """
    labels: dict[tuple[date, date], int] = {}

    for _concept, _unit, row in _rows(payload):
        if row.get("form") not in ANNUAL_FORMS:
            continue
        start, end = _as_date(row.get("start")), _as_date(row.get("end"))
        fiscal_year = row.get("fy")
        if start is None or end is None or not isinstance(fiscal_year, int):
            continue
        if not MIN_FISCAL_YEAR_DAYS <= (end - start).days + 1 <= MAX_FISCAL_YEAR_DAYS:
            continue
        # A comparative in a much later filing carries that filing's fiscal
        # year, not the window's. Only the year's own report can name it.
        if abs(fiscal_year - end.year) > MAX_LABEL_DRIFT:
            continue

        window = (start, end)
        held = labels.get(window)
        if held is None or fiscal_year < held:
            labels[window] = fiscal_year

    windows = sorted(
        FiscalYearWindow(fiscal_year=year, start=start, end=end)
        for (start, end), year in labels.items()
    )
    declared = list(_without_overlaps(_one_window_per_year(windows)))
    return FiscalCalendar(tuple(declared) + _year_in_progress(payload, declared))


def _year_in_progress(
    payload: dict[str, Any],
    declared: list[FiscalYearWindow],
) -> tuple[FiscalYearWindow, ...]:
    """The fiscal year being reported but not yet closed.

    Without this the most recent quarters — the ones a reader actually opens the
    product for — classify as nothing, because the annual report that would
    declare the year's end has not been filed. Apple stops at fiscal 2025 while
    reporting fiscal 2026.

    The year's **start is observed**, not guessed: every quarterly report opens
    its cash flow and income statements with a year-to-date window running from
    the fiscal year start. The earliest such start after the last declared year
    is the new year's first day.

    Only the end is carried over, from the preceding year's length, and the
    window is marked `is_projected` so nothing downstream can mistake it for a
    figure the company stated.
    """
    if not declared:
        return ()

    last = declared[-1]
    starts: dict[date, int] = {}

    for _concept, _unit, row in _rows(payload):
        start, end = _as_date(row.get("start")), _as_date(row.get("end"))
        fiscal_year = row.get("fy")
        if start is None or end is None or not isinstance(fiscal_year, int):
            continue
        if start <= last.end or end <= last.end:
            continue
        # A year-to-date window opens the fiscal year. Discrete quarters open
        # later, so the earliest start seen is the year's first day.
        if start not in starts or fiscal_year < starts[start]:
            starts[start] = fiscal_year

    if not starts:
        return ()

    start = min(starts)
    return (
        FiscalYearWindow(
            fiscal_year=starts[start],
            start=start,
            end=start + timedelta(days=last.days - 1),
            is_projected=True,
        ),
    )


def _one_window_per_year(windows: list[FiscalYearWindow]) -> list[FiscalYearWindow]:
    """Keep the window each label most plausibly belongs to, and drop the rest.

    Two windows claiming the same fiscal year means the label came from a
    comparative rather than from the year's own annual report — which is what
    happens for any year older than the filings we fetched. Apple ended up with
    fiscal 2008 and fiscal 2009 both called 2009, and four different years'
    revenue landed in one period as a result.

    The window whose own end year matches its label wins, because that is the
    one a real annual report would have named. Where that still ties, the later
    window wins: labels drift upward, never down.

    Dropping the loser is the point. We cannot say which year the other window
    is, and a period labelled with a year it is not produces a growth rate that
    is confidently, unrecoverably wrong.
    """

    def rank(window: FiscalYearWindow) -> tuple[int, object]:
        """Lower is better: the label's drift first, then the later window."""
        return (abs(window.fiscal_year - window.end.year), -window.end.toordinal())

    best: dict[int, FiscalYearWindow] = {}
    for window in windows:
        held = best.get(window.fiscal_year)
        if held is None or rank(window) < rank(held):
            best[window.fiscal_year] = window
    return sorted(best.values())


def _without_overlaps(windows: list[FiscalYearWindow]) -> Iterator[FiscalYearWindow]:
    """Drop any window that overlaps one already accepted.

    A company that changes its year end files a transition period which can sit
    inside a neighbouring year. Keeping both would let one date classify as two
    different quarters, so the earlier, already-established year wins and the
    overlap is skipped rather than guessed at.
    """
    last_end: date | None = None
    for window in windows:
        if last_end is not None and window.start <= last_end:
            continue
        yield window
        last_end = window.end


def parse_company_facts(payload: bytes, provider_entity_id: str) -> list[ProviderFact]:
    """Every fact in a `companyfacts` response, kept close to the source.

    Periods are carried as the provider expressed them. Deciding which fiscal
    quarter a range belongs to is domain logic and happens in `financial_core`,
    against the calendar `learn_fiscal_calendar` reconstructs.
    """
    document = json.loads(payload)
    facts: list[ProviderFact] = []

    for concept, unit, row in _rows(document):
        end = _as_date(row.get("end"))
        if end is None:
            continue
        start = _as_date(row.get("start"))

        value = row.get("val")
        facts.append(
            ProviderFact(
                provider_entity_id=provider_entity_id,
                provider_filing_id=str(row.get("accn") or ""),
                concept=concept,
                period=ProviderPeriod(
                    kind="duration" if start is not None else "instant",
                    start=start,
                    end=end,
                    raw=f"{row.get('start') or ''}/{row.get('end')}",
                ),
                value=float(value) if isinstance(value, int | float) else None,
                unit=unit,
                scale=None,
                decimals=None,
                statement=None,
                labels={"form": str(row.get("form") or ""), "filed": str(row.get("filed") or "")},
            )
        )

    return facts


def concept_coverage(payload: dict[str, Any]) -> dict[str, int]:
    """How many rows each concept carries. Used to survey a taxonomy."""
    counts: dict[str, int] = defaultdict(int)
    for concept, _unit, _row in _rows(payload):
        counts[concept] += 1
    return dict(counts)
