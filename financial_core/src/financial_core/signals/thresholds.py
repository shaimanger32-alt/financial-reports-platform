"""Thresholds, as versioned data rather than numbers buried in logic.

Spec section 0, rule 8 forbids hard-coding financial thresholds into business
logic, and section 17 sets out what one has to carry: the metric it applies to,
its sector and stage scope, absolute and relative levels, how many periods it
needs, a severity and a version.

Two levels do the work here, and they play different roles:

* `deviation` — how far from the company's own norm the value has to sit. This
  is the primary test and needs no market knowledge, because the company
  calibrates it (section 17, priority two).
* `minimum_magnitude` — a floor below which a move is not worth a sentence even
  if it is statistically unusual. A collection period that moves from 40.0 to
  40.4 days is a rounding artefact at a company that never moves at all.

The floor is the only genuinely judgemental number, which is why it is data
here, carries a version, and is recorded in docs/financial-methodology.md rather
than being asserted in code.
"""

from dataclasses import dataclass
from typing import Final

from financial_core.signals.model import Severity

THRESHOLD_VERSION: Final[str] = "v1"


@dataclass(frozen=True, slots=True)
class Threshold:
    """When a movement in one metric is worth reporting."""

    metric_code: str
    deviation: float
    """Robust units away from the company's own median. See `baseline`."""
    minimum_magnitude: float = 0.0
    """Absolute change below which the move is noise regardless of deviation."""
    minimum_periods: int = 1
    """How many consecutive periods the condition must hold."""
    severity: Severity = Severity.WATCH
    sector_scope: str = "general"
    company_stage_scope: str | None = None
    version: str = THRESHOLD_VERSION

    def is_breached(self, deviation: float | None, magnitude: float, periods: int) -> bool:
        """Whether an observation clears every bar this threshold sets.

        A missing deviation means the history is too short to judge, which is not
        the same as the condition failing — but it is also not grounds for
        raising a signal, so it returns False.
        """
        if deviation is None:
            return False
        return (
            abs(deviation) >= self.deviation
            and abs(magnitude) >= self.minimum_magnitude
            and periods >= self.minimum_periods
        )


class ThresholdSet:
    """The thresholds in force, keyed by metric and sector."""

    def __init__(self, thresholds: tuple[Threshold, ...], version: str = THRESHOLD_VERSION) -> None:
        self._thresholds = thresholds
        self.version = version

    def for_metric(self, metric_code: str, sector: str | None = None) -> Threshold | None:
        """The most specific threshold that applies, or None if none does.

        A sector-specific entry wins over the general one, which is how spec
        section 18 keeps a retailer's negative working capital from being read
        with a manufacturer's expectations.
        """
        candidates = [t for t in self._thresholds if t.metric_code == metric_code]
        if not candidates:
            return None

        if sector:
            specific = [t for t in candidates if t.sector_scope == sector]
            if specific:
                return specific[0]

        general = [t for t in candidates if t.sector_scope == "general"]
        return general[0] if general else None

    def __len__(self) -> int:
        return len(self._thresholds)

    def __iter__(self) -> object:
        return iter(self._thresholds)
