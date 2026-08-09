"""Parsing of MAGNA's `Period` column.

MAGNA expresses a period in one of two shapes:

    "31/12/2022"                instant  -- a balance sheet date
    "01/01/2022 - 31/03/2022"   duration -- an income or cash flow window

Both shapes appear in the same column, so the distinction between a stock and a
flow is recoverable from the payload alone. That distinction is the reason spec
section 11.3 separates `instant` from `duration`, and getting it wrong silently
corrupts every ratio that mixes the two.

No fiscal-quarter semantics are assigned here. Deciding that
`01/04/2024 - 30/06/2024` is "Q2 2024 discrete" while `01/01/2024 - 30/06/2024`
is "H1 2024 cumulative" is domain logic and belongs in financial_core.
"""

import re
from datetime import date

from ingestion.providers.base import ProviderPeriod

_DATE = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\s*$")
_RANGE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})\s*$")


class PeriodParseError(ValueError):
    """The `Period` column did not match any known MAGNA shape."""


def _to_date(value: str) -> date:
    match = _DATE.match(value)
    if not match:
        raise PeriodParseError(f"not a dd/mm/yyyy date: {value!r}")
    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise PeriodParseError(f"impossible date: {value!r}") from exc


def parse_period(raw: str) -> ProviderPeriod:
    """Turn a MAGNA `Period` string into a structured period.

    Raises PeriodParseError rather than guessing. A period we cannot read is a
    fact we must not use.
    """
    if not raw or not raw.strip():
        raise PeriodParseError("empty period")

    range_match = _RANGE.match(raw)
    if range_match:
        start = _to_date(range_match.group(1))
        end = _to_date(range_match.group(2))
        if end < start:
            raise PeriodParseError(f"period ends before it starts: {raw!r}")
        return ProviderPeriod(kind="duration", start=start, end=end, raw=raw.strip())

    return ProviderPeriod(kind="instant", start=None, end=_to_date(raw), raw=raw.strip())
