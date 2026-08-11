"""What a signal is, and what it is not.

Spec section 15: a signal is a numeric observation. It is never a cause and never
an accusation. "Collection has lengthened" is a signal; "the company is stuffing
the channel" is not, and no amount of arithmetic turns the first into the second.

Section 20 sets the confidence model: it classifies how much evidence stands
behind an observation, and is explicitly not a statistical probability.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from financial_core.periods import FiscalPeriod


class Direction(StrEnum):
    """Which way the number moved, before any judgement about whether that is good."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class Severity(StrEnum):
    """How much attention an observation deserves.

    Separate from direction on purpose: a rising figure can be reassuring or
    alarming depending on which figure it is, and conflating the two is how a
    dashboard ends up calling growth a warning.
    """

    INFO = "info"
    POSITIVE = "positive"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def is_concerning(self) -> bool:
        return self in {Severity.WATCH, Severity.WARNING, Severity.CRITICAL}


class Confidence(StrEnum):
    """How much stands behind an observation (spec section 20).

    A product classification, not a probability. Nothing here should ever be
    rendered as a percentage.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class Signal:
    """One numeric observation about one company in one period."""

    code: str
    period: FiscalPeriod
    metric_code: str
    direction: Direction
    severity: Severity
    confidence: Confidence
    rule_version: str
    value: float | None = None
    baseline: float | None = None
    deviation: float | None = None
    """How far the value sits from the company's own norm, in robust units."""
    periods_persisted: int = 1
    message_key: str = ""
    """Key into the localised phrasing. The wording itself never lives in the
    engine, so a signal cannot accidentally carry a causal claim (section 42)."""
    inputs: dict[str, float | None] = field(default_factory=dict)

    @property
    def is_concerning(self) -> bool:
        return self.severity.is_concerning
