"""The pattern rules, as data.

Spec section 16 asks for pattern rules that are "data/config driven ככל שניתן"
and lists exactly what one carries: a code, a sector scope, required and
optional signals, a minimum number of required matches, a minimum persistence,
a severity, a template key and a version. Those are the fields below, and adding
or retuning a pattern is a change to this table rather than to logic.

Patterns are tiered like the signals they combine. A `CORE` pattern rests only
on metrics every issuer tags, so it can fire for any company in the market. An
`EXTENDED` one is silent wherever its metrics are null, which is the honest
outcome rather than a gap to paper over (decision 0010).

**No sentences here.** A `message_key` points at wording in
`apps/web/src/lib/messages.ts`, which is what keeps section 42 reviewable as one
file instead of an audit of the codebase.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from financial_core.metrics.catalogue import MetricTier
from financial_core.signals.model import Severity

PATTERN_VERSION: Final[str] = "v2"


class Comparison(StrEnum):
    """How a metric's value is tested against a threshold."""

    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"


@dataclass(frozen=True, slots=True)
class MetricCondition:
    """A condition on a computed metric's value.

    Signals answer "is this move unlike the company's usual?", which is a
    comparison against its own history. Some premises are not that question at
    all: P2's wording rests on profit having *risen*, and a company whose profit
    grows steadily every year never raises an unusual-growth signal while its
    profit rises the whole time. Expressing that premise as a signal would say
    something different from what the pattern claims.

    A null value never satisfies a condition. Missing data is not a small value
    (non-negotiable 1), and a premise that cannot be checked has not been met.
    """

    metric_code: str
    comparison: Comparison
    threshold: float
    note: str | None = None

    def is_met_by(self, value: float | None) -> bool:
        if value is None:
            return False
        match self.comparison:
            case Comparison.GREATER_THAN:
                return value > self.threshold
            case Comparison.GREATER_OR_EQUAL:
                return value >= self.threshold
            case Comparison.LESS_THAN:
                return value < self.threshold
            case Comparison.LESS_OR_EQUAL:
                return value <= self.threshold


@dataclass(frozen=True, slots=True)
class PatternRule:
    """One combination of signals worth reading as a single thing."""

    code: str
    required_signals: tuple[str, ...]
    """The pool the pattern is drawn from. `minimum_required` of these must have
    fired; the rule does not demand all of them."""
    minimum_required: int
    message_key: str
    tier: MetricTier = MetricTier.EXTENDED
    prerequisite_signals: tuple[str, ...] = ()
    """Signals that must **all** have fired for the pattern to mean what its
    wording says. A field section 16 does not list, added because P1 cannot be
    expressed without it: its premise is that revenue grew, and a rule that only
    counts matches out of one pool would fire it on a company whose collection
    lengthened while revenue did not grow at all. The reader would then be told
    that growth needs checking at a company that did not grow. A pattern may not
    assert something the signals did not observe (section 42)."""
    prerequisite_metrics: tuple[MetricCondition, ...] = ()
    """Conditions on metric values that must **all** hold, alongside
    `prerequisite_signals`. Same role — the premise the wording rests on — for a
    premise that is a fact about the level rather than about how unusual the move
    was. The engine still concludes nothing the metrics did not already say; it
    reads a computed value and compares it with a named constant."""
    dependent_signal_groups: tuple[frozenset[str], ...] = ()
    """Sets of member signals that are not independent evidence of each other.

    Two signals derived from the same inputs are one observation seen twice, and
    counting them as two corroborating views would inflate confidence the data
    did not earn. The engine records which groups a pattern leaned on, so a
    reader of the payload can tell corroboration from restatement of the same
    arithmetic (spec section 20)."""
    optional_signals: tuple[str, ...] = ()
    """Signals that corroborate the pattern and are recorded when present, but
    never decide whether it fires."""
    variant_message_keys: tuple[tuple[MetricCondition, str], ...] = ()
    """Alternative wording keys, each guarded by a condition, first match wins.

    One pattern can be true in two ways that a reader would not describe with the
    same sentence: profit outrunning cash flow is not the same event as profit
    rising while cash flow falls. The engine selects a key and never a sentence,
    so section 42 still holds."""
    minimum_periods: int = 1
    """How long the strongest member signal must have persisted."""
    severity: Severity | None = None
    """Overrides the severity taken from the member signals. Left as None the
    pattern is as severe as the most severe observation in it, which stops a
    rule from quietly inflating what the numbers said."""
    sector_scope: str = "general"
    version: str = PATTERN_VERSION
    note: str | None = None

    @property
    def is_core(self) -> bool:
        return self.tier is MetricTier.CORE


# --- P2 -----------------------------------------------------------------------
#
# DECIDED BY SHAY, 2026-08-14. The literal reading of spec section 16, with
# rising profit as a hard premise rather than as corroboration.
#
# The rule was first written on the divergence alone, because at the time the
# only case in the data was Hilan 2025-Q4, whose profit *fell* 1.9%, and
# requiring profit to rise would have left the pattern silent everywhere it
# could be checked. Forty-two American companies later that argument is gone:
# the literal reading fires on 13 of the 19 periods the looser rule matched.
#
# What decided it was not coverage but wording. P2 says profit rose and cash did
# not follow. Where profit and cash flow both fell, the event is deterioration,
# and the sentence would be false. A pattern may not assert something the
# numbers do not support, whatever it costs in matches.

_PROFIT_ROSE: Final[MetricCondition] = MetricCondition(
    metric_code="net_income_growth_yoy",
    comparison=Comparison.GREATER_THAN,
    threshold=0.0,
    note="A ratio, so zero is the sign boundary and not a tuned threshold. "
    "Profit that fell 1.9% is not profit that rose, and no tolerance band is "
    "applied to keep a historical case: that would be fitting the definition of "
    "the phenomenon to one company.",
)

_CASH_FLOW_FELL: Final[MetricCondition] = MetricCondition(
    metric_code="operating_cash_flow_growth_yoy",
    comparison=Comparison.LESS_THAN,
    threshold=0.0,
    note="Selects the wording only. Cash flow that fell outright and cash flow "
    "that grew more slowly than profit are both P2, and a reader would not "
    "describe them with the same sentence. Reading the sign is safe because a "
    "growth ratio is null whenever its base was not positive (section 13.1), so "
    "a negative value can only mean a fall from a positive base — never an "
    "improvement measured from a negative one.",
)

CORE_PATTERNS: Final[tuple[PatternRule, ...]] = (
    PatternRule(
        code="P2_EARNINGS_QUALITY",
        prerequisite_metrics=(_PROFIT_ROSE,),
        required_signals=(
            "SIG_EARNINGS_CASH_DIVERGENCE",
            "SIG_ACCRUALS_ELEVATED",
            "SIG_OPERATING_CASH_DETERIORATION",
        ),
        minimum_required=2,
        # `cash_conversion` is OCF over net income; `accruals_proxy` is net
        # income less OCF over average assets. Both are functions of the same two
        # inputs, so when the gap widens they move together as a matter of
        # arithmetic rather than as two findings. The methodology already
        # describes Hilan's pair as "the same event measured from two sides".
        dependent_signal_groups=(
            frozenset({"SIG_EARNINGS_CASH_DIVERGENCE", "SIG_ACCRUALS_ELEVATED"}),
        ),
        message_key="pattern.earnings_quality",
        variant_message_keys=((_CASH_FLOW_FELL, "pattern.earnings_quality.cash_declined"),),
        tier=MetricTier.CORE,
        optional_signals=("SIG_PROFIT_ACCELERATION",),
        note="Every input is a concept all issuers tag, so this pattern works "
        "for any company including banks (decision 0010). It reports a gap "
        "between profit and cash. It is never an allegation that the profit is "
        "wrong, and section 42 forbids reading intent into it.",
    ),
)

# --- P1 -----------------------------------------------------------------------
#
# Section 16 lists revenue up, DSO up, a material receivables growth gap and
# gross margin down, and its own output sentence reads "הגבייה התארכה **ו/או**
# המרווח נשחק". That "and/or" is the rule: growth is the premise, and one
# quality concern alongside it is the pattern. The threshold is the spec's, not
# an invented one.
#
# Every input is EXTENDED. Revenue is tagged by 86% of issuers and gross profit
# by 69% (decision 0010), so P1 is silent for a financial company by
# construction — which is correct, not a gap.

EXTENDED_PATTERNS: Final[tuple[PatternRule, ...]] = (
    PatternRule(
        code="P1_GROWTH_QUALITY",
        prerequisite_signals=("SIG_REVENUE_ACCELERATION",),
        required_signals=(
            "SIG_DSO_DETERIORATION",
            "SIG_RECEIVABLES_GROWTH_GAP",
            "SIG_MARGIN_COMPRESSION",
        ),
        minimum_required=1,
        message_key="pattern.growth_quality",
        note="Reports that growth arrived alongside slower collection or a "
        "thinner margin. Section 16 forbids the obvious next sentence: this "
        "never predicts that revenue will fall, and never suggests the revenue "
        "was pulled forward or the customers cannot pay.",
    ),
)

ALL_PATTERNS: Final[tuple[PatternRule, ...]] = (*CORE_PATTERNS, *EXTENDED_PATTERNS)
PATTERNS_BY_CODE: Final[dict[str, PatternRule]] = {rule.code: rule for rule in ALL_PATTERNS}
