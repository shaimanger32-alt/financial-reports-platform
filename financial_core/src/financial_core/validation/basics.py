"""Basic validation (spec section 21.1).

The checks that need no accounting knowledge at all: is this figure the same
unit as the last one, are two filings claiming different values for the same
line in the same filing, and is this number one that cannot exist.

The last of those is where restraint matters. Section 21.1 says impossible
values "כאשר באמת בלתי אפשריים" — **when they truly are impossible** — and the
qualifier is the whole instruction. Revenue looks like it cannot be negative
until a quarter of heavy returns makes it so. Equity looks like it cannot be
negative until a company buys back more stock than it has retained. Operating
profit is negative at half the market on a bad year.

So the list below is short on purpose. It contains only quantities that cannot
be negative without the figure being wrong rather than the company being in
trouble: you cannot own less than nothing, hold less than no cash, or have
fewer than no shares outstanding. Everything else that looks alarming is the
signal engine's business, not this module's.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

BASICS_VERSION: Final[str] = "v1"

# Quantities that are a count or a stock of something owned. A negative one is
# an error in the figure, never a fact about the business.
#
# Deliberately excluded, because a negative value is real and meaningful:
# every profit line, every cash flow subtotal, working capital, net debt,
# equity (a company can have a deficit), and every growth rate.
NON_NEGATIVE_METRICS: Final[frozenset[str]] = frozenset(
    {
        "total_assets",
        "current_assets",
        "non_current_assets",
        "cash_and_equivalents",
        "inventories",
        "trade_receivables",
        "property_plant_equipment",
        "weighted_average_shares_basic",
        "weighted_average_shares_diluted",
    }
)

# A company cannot have no assets at all and still be filing.
POSITIVE_METRICS: Final[frozenset[str]] = frozenset({"total_assets"})


class BasicIssue(StrEnum):
    """What basic validation found."""

    IMPOSSIBLE_VALUE = "impossible_value"
    """A quantity that cannot be negative, or an asset base of nothing."""

    UNIT_CHANGED = "unit_changed"
    """The same metric reported in two different units. Either the company
    changed reporting currency — a comparability warning under section 21.3 —
    or a concept chain resolved to something measured differently."""

    CONTRADICTORY_DUPLICATE = "contradictory_duplicate"
    """One filing reporting one line for one period twice, with two values.
    Distinct from a restatement, which is two *different* filings disagreeing
    and is a real event; this is a single document contradicting itself."""


@dataclass(frozen=True, slots=True)
class BasicFinding:
    """One thing basic validation noticed."""

    issue: BasicIssue
    metric_code: str
    period_code: str
    detail: str
    values: tuple[float, ...] = ()
    version: str = BASICS_VERSION


@dataclass(frozen=True, slots=True)
class Observation:
    """One reported figure, reduced to what basic validation needs.

    Deliberately not a `FactPoint`: these checks run over everything the store
    holds, including the figures a `FactSet` discards when it picks a winner,
    because a contradiction between two of them is exactly what is being looked
    for.
    """

    metric_code: str
    period_code: str
    value: float
    unit: str | None = None
    filing: str = ""
    raw_concept: str = ""
    """The tag the issuer actually used. Duplicates are judged per concept, not
    per metric: two concepts in one fallback chain reporting different values is
    the chain doing its job, not a filing contradicting itself. `net_income`
    resolves through both `ProfitLoss` and `NetIncomeLoss`, and they differ by
    the minority interest at every company that has one."""


def check_impossible_values(observations: Iterable[Observation]) -> list[BasicFinding]:
    """Figures that cannot be what they say they are."""
    findings: list[BasicFinding] = []
    for observation in observations:
        if observation.metric_code in NON_NEGATIVE_METRICS and observation.value < 0:
            findings.append(
                BasicFinding(
                    issue=BasicIssue.IMPOSSIBLE_VALUE,
                    metric_code=observation.metric_code,
                    period_code=observation.period_code,
                    detail="negative, and this quantity cannot be",
                    values=(observation.value,),
                )
            )
        elif observation.metric_code in POSITIVE_METRICS and observation.value == 0:
            findings.append(
                BasicFinding(
                    issue=BasicIssue.IMPOSSIBLE_VALUE,
                    metric_code=observation.metric_code,
                    period_code=observation.period_code,
                    detail="zero, and a filing company has assets",
                    values=(observation.value,),
                )
            )
    return findings


def check_unit_consistency(observations: Iterable[Observation]) -> list[BasicFinding]:
    """One metric reported in two units across a company's history.

    A currency change is a real event and section 21.3 wants it flagged. A unit
    change with no currency change is ours: a chain resolving to a concept
    measured in shares where the metric is money, say.
    """
    units: dict[str, dict[str, set[str]]] = {}
    for observation in observations:
        if observation.unit is None:
            continue
        units.setdefault(observation.metric_code, {}).setdefault(observation.unit, set()).add(
            observation.period_code
        )

    findings: list[BasicFinding] = []
    for metric_code, by_unit in sorted(units.items()):
        if len(by_unit) < 2:
            continue
        listed = ", ".join(sorted(by_unit))
        findings.append(
            BasicFinding(
                issue=BasicIssue.UNIT_CHANGED,
                metric_code=metric_code,
                period_code="",
                detail=f"reported in more than one unit: {listed}",
            )
        )
    return findings


def check_contradictory_duplicates(observations: Iterable[Observation]) -> list[BasicFinding]:
    """One filing giving one line two different values for one period.

    Not a restatement. A restatement is a later filing revising an earlier one,
    which is a real event and is reported separately. This is a single document
    disagreeing with itself, which is either a tagging error at the issuer or a
    parsing error of ours — and both are worth knowing about.
    """
    seen: dict[tuple[str, str, str, str], set[float]] = {}
    for observation in observations:
        if not observation.filing or not observation.raw_concept:
            continue
        key = (
            observation.filing,
            observation.raw_concept,
            observation.metric_code,
            observation.period_code,
        )
        seen.setdefault(key, set()).add(observation.value)

    findings: list[BasicFinding] = []
    for (filing, concept, metric_code, period_code), values in sorted(seen.items()):
        if len(values) < 2:
            continue
        findings.append(
            BasicFinding(
                issue=BasicIssue.CONTRADICTORY_DUPLICATE,
                metric_code=metric_code,
                period_code=period_code,
                detail=f"{filing} reports {concept} twice for this period, with different values",
                values=tuple(sorted(values)),
            )
        )
    return findings


def check_basics(observations: Sequence[Observation]) -> list[BasicFinding]:
    """Every basic check, over one company's reported figures."""
    return [
        *check_impossible_values(observations),
        *check_unit_consistency(observations),
        *check_contradictory_duplicates(observations),
    ]
