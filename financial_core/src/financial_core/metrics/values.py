"""The figures a calculation works from.

The metric engine never touches a database. It is handed a `FactSet` -- a plain
in-memory view of one company's numbers -- and everything it produces is a pure
function of that. This is what spec section 9 asks for: calculations testable
without FastAPI or a database.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from financial_core.periods import DurationKind, FiscalPeriod, PeriodKind
from financial_core.provenance import Origin
from financial_core.quality import QualityStatus


@dataclass(frozen=True, slots=True)
class FactPoint:
    """One figure, with enough context to explain where it came from."""

    metric_code: str
    period: FiscalPeriod
    value: float
    raw_concept: str
    origin: Origin = Origin.REPORTED
    quality: QualityStatus = QualityStatus.VERIFIED
    priority: int = 0
    """Position of `raw_concept` in its metric's fallback chain. Lower is more
    precise (decision 0009)."""

    @property
    def is_analysable(self) -> bool:
        return self.quality.is_analysable


def _outranks(candidate: FactPoint, held: FactPoint) -> bool:
    """Whether `candidate` should replace `held` for the same metric and period.

    Two rules, in order:

    1. A figure the issuer reported beats one we derived. Ours never displaces
       theirs (decision 0009).
    2. Otherwise the more precise concept wins, which is the one earlier in the
       fallback chain.
    """
    if candidate.origin is not held.origin:
        return candidate.origin is Origin.REPORTED
    return candidate.priority < held.priority


class FactSet:
    """Every usable figure for one company, indexed for lookup.

    Figures whose quality status rules them out of analysis are rejected on the
    way in, so a calculation cannot accidentally consume one (spec section 21.4).
    """

    def __init__(self, points: Iterable[FactPoint]) -> None:
        self._by_key: dict[tuple[str, str], FactPoint] = {}
        for point in points:
            if not point.is_analysable:
                continue
            key = (point.metric_code, point.period.code)
            held = self._by_key.get(key)
            if held is None or _outranks(point, held):
                self._by_key[key] = point

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self) -> Iterator[FactPoint]:
        return iter(self._by_key.values())

    def point(self, metric_code: str, period: FiscalPeriod) -> FactPoint | None:
        """The figure for one metric in one period, or None if unknown."""
        return self._by_key.get((metric_code, period.code))

    def value(self, metric_code: str, period: FiscalPeriod) -> float | None:
        """The number alone. None means unknown, never zero (spec section 4.4)."""
        point = self.point(metric_code, period)
        return None if point is None else point.value

    def has(self, metric_code: str, period: FiscalPeriod) -> bool:
        return (metric_code, period.code) in self._by_key

    def periods(
        self,
        metric_code: str | None = None,
        *,
        period_kind: PeriodKind | None = None,
        duration_kind: DurationKind | None = None,
    ) -> list[FiscalPeriod]:
        """Periods that carry data, oldest first."""
        found = {
            point.period
            for point in self._by_key.values()
            if (metric_code is None or point.metric_code == metric_code)
            and (period_kind is None or point.period.period_kind is period_kind)
            and (duration_kind is None or point.period.duration_kind is duration_kind)
        }
        return sorted(found)

    def metrics(self) -> set[str]:
        return {point.metric_code for point in self._by_key.values()}
