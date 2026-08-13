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
from typing import Final

from financial_core.metrics.catalogue import MetricTier
from financial_core.signals.model import Severity

PATTERN_VERSION: Final[str] = "v1"


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
    optional_signals: tuple[str, ...] = ()
    """Signals that corroborate the pattern and are recorded when present, but
    never decide whether it fires."""
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
# PENDING SHAY'S CONFIRMATION. Spec section 16 words P2 as "Net Income ↑ with
# OCF ↓", and taken literally that rule does not fire on the one case in the
# data it was written for: Hilan 2025-Q4 has cash conversion down 0.26 against a
# usual +0.17, accruals up 2.23pp against a usual -1.62pp — and net income down
# 1.9%. Requiring profit to rise would leave the pattern silent everywhere we
# can currently check it.
#
# So the rule below is written on the divergence itself rather than on the
# direction of profit: two of the three views of the gap between accounting
# profit and cash. Flipping this back to the literal reading is a change to
# `required_signals` and `minimum_required` on this one rule.

CORE_PATTERNS: Final[tuple[PatternRule, ...]] = (
    PatternRule(
        code="P2_EARNINGS_QUALITY",
        required_signals=(
            "SIG_EARNINGS_CASH_DIVERGENCE",
            "SIG_ACCRUALS_ELEVATED",
            "SIG_OPERATING_CASH_DETERIORATION",
        ),
        minimum_required=2,
        message_key="pattern.earnings_quality",
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
