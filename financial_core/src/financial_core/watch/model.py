"""What a watch item is.

Spec section 28. A pattern says something about one period; a watch item is what
carries it into the next one. "Inventory outgrew sales and the days lengthened"
becomes "check next quarter whether inventory returns to a pace matching sales",
and the quarter after that answers it.

That continuity is the only place the product holds an opinion across time, so
the rules for it are narrow. A watch item never predicts and never advises. It
records what was observed, what the same measurement says now, and whether the
distance between them grew or shrank — nothing beyond that.

**Section 11.10 gives the fields; the statuses carry the judgement.** Two of them
are easy to get wrong and are worth stating plainly:

* `resolved` means the condition that opened the item no longer holds. It is a
  measurement, not an all-clear.
* `not_measurable` means this period could not answer the question. It is never
  a quiet `resolved`: an item whose metric went null is still open business, and
  closing it because the data disappeared would be the one failure mode that
  makes report memory worse than having none.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class WatchStatus(StrEnum):
    """Where a watch item stands, as of the period that last reviewed it."""

    OPEN = "open"
    """Raised, and nothing later has said whether it improved or worsened."""

    IMPROVED = "improved"
    """The move that raised it has narrowed, and has not returned to normal."""

    WORSENED = "worsened"
    """The move that raised it has widened."""

    RESOLVED = "resolved"
    """The condition no longer holds: the signal that raised it stopped firing."""

    NOT_MEASURABLE = "not_measurable"
    """This period could not answer the question. Not a resolution."""

    @property
    def is_closed(self) -> bool:
        """Only a resolution closes an item. `not_measurable` is a pause."""
        return self is WatchStatus.RESOLVED


@dataclass(frozen=True, slots=True)
class WatchObservation:
    """One metric's reading at one point in the item's life.

    Both the value and the year-on-year change are kept. The value is what a
    reader recognises; the change is what the item is actually about, since a
    signal is raised on the move rather than on the level.
    """

    metric_code: str
    period_code: str
    value: float | None
    year_on_year_change: float | None
    deviation: float | None
    """Robust units from the company's own median, as the signal engine measured
    it. Null where the history was too short to say."""


@dataclass(frozen=True, slots=True)
class WatchItem:
    """One thing worth looking at again in the next report.

    Section 11.10's shape, with the provenance a reader needs to check it:
    the pattern that raised it, the period it was raised in, what the metric
    read then, what it reads now, and why the status is what it is.
    """

    company_id: str
    source_code: str
    """The pattern or signal code that raised it. A watch item is never raised
    from nothing; it always points back at an observation that was already made
    and already shown."""
    opened_in_period: str
    opened_from: WatchObservation
    """The reading that raised it. Never overwritten — an item that forgets what
    it was opened on cannot be audited, and cannot say whether things improved."""
    status: WatchStatus = WatchStatus.OPEN
    reviewed_in_period: str | None = None
    current: WatchObservation | None = None
    """The same metric as of the reviewing period. None until first reviewed."""
    resolved_in_period: str | None = None
    status_reason: str = ""
    """A message key, never a sentence (spec section 42)."""
    history: tuple[tuple[str, WatchStatus], ...] = field(default_factory=tuple)
    """Every period that reviewed this item and what it concluded, oldest first.
    A `not_measurable` gap between two readings is part of the record rather than
    something to smooth over."""

    @property
    def is_open_business(self) -> bool:
        return not self.status.is_closed
