"""The signal rules, as data.

Spec section 16 asks for rules that are data-driven rather than coded, so that
adding or retuning one is a change to a table and not to logic.

Every rule names the metric it watches, the direction it cares about, and a
message key. **The wording never lives here.** That is deliberate: section 42
draws a hard line between "collection has lengthened" and "the company is
stuffing the channel", and an engine that carries no sentences cannot cross it.

Rules are tiered like the metrics they watch. A `CORE` rule works for every
company because its metric does; an `EXTENDED` rule is silent where the metric
is null, which is the honest outcome rather than a gap to paper over.
"""

from dataclasses import dataclass
from typing import Final

from financial_core.metrics.catalogue import MetricTier
from financial_core.signals.model import Direction, Severity

RULE_VERSION: Final[str] = "v1"


@dataclass(frozen=True, slots=True)
class SignalRule:
    """One thing worth noticing about one metric."""

    code: str
    metric_code: str
    concerning_direction: Direction
    message_key: str
    tier: MetricTier = MetricTier.EXTENDED
    severity: Severity | None = None
    """Overrides the threshold's severity when the rule itself decides it, as a
    positive observation does."""
    version: str = RULE_VERSION
    note: str | None = None

    @property
    def is_core(self) -> bool:
        return self.tier is MetricTier.CORE


CORE_RULES: Final[tuple[SignalRule, ...]] = (
    SignalRule(
        "SIG_LIQUIDITY_DETERIORATION",
        "current_ratio",
        Direction.DOWN,
        "signal.liquidity_deterioration",
        MetricTier.CORE,
        note="Weakening liquidity. Never a claim about solvency or a covenant.",
    ),
    SignalRule(
        "SIG_LEVERAGE_INCREASE",
        "liabilities_to_equity",
        Direction.UP,
        "signal.leverage_increase",
        MetricTier.CORE,
    ),
    SignalRule(
        "SIG_EQUITY_EROSION",
        "equity_ratio",
        Direction.DOWN,
        "signal.equity_erosion",
        MetricTier.CORE,
    ),
    SignalRule(
        "SIG_EARNINGS_CASH_DIVERGENCE",
        "cash_conversion",
        Direction.DOWN,
        "signal.earnings_cash_divergence",
        MetricTier.CORE,
        note="Profit is converting to cash less well than it did. Not a claim "
        "that the profit is wrong.",
    ),
    SignalRule(
        "SIG_ACCRUALS_ELEVATED",
        "accruals_proxy",
        Direction.UP,
        "signal.accruals_elevated",
        MetricTier.CORE,
        note="Spec section 13.3: a signal only. It is never translated into an "
        "allegation of manipulation.",
    ),
    SignalRule(
        "SIG_OPERATING_CASH_DETERIORATION",
        "operating_cash_flow_growth_yoy",
        Direction.DOWN,
        "signal.operating_cash_deterioration",
        MetricTier.CORE,
    ),
    SignalRule(
        "SIG_PROFIT_ACCELERATION",
        "net_income_growth_yoy",
        Direction.UP,
        "signal.profit_acceleration",
        MetricTier.CORE,
        severity=Severity.POSITIVE,
    ),
    SignalRule(
        "SIG_TAX_RATE_INCREASE",
        "effective_tax_rate",
        Direction.UP,
        "signal.tax_rate_increase",
        MetricTier.CORE,
        severity=Severity.INFO,
        note="Often a one-off or a change in mix. Informational, not a warning.",
    ),
)

EXTENDED_RULES: Final[tuple[SignalRule, ...]] = (
    SignalRule(
        "SIG_REVENUE_ACCELERATION",
        "revenue_growth_yoy",
        Direction.UP,
        "signal.revenue_acceleration",
        severity=Severity.POSITIVE,
    ),
    SignalRule(
        "SIG_MARGIN_EXPANSION",
        "operating_margin",
        Direction.UP,
        "signal.margin_expansion",
        severity=Severity.POSITIVE,
    ),
    SignalRule(
        "SIG_MARGIN_COMPRESSION",
        "gross_margin",
        Direction.DOWN,
        "signal.margin_compression",
    ),
    SignalRule(
        "SIG_DSO_DETERIORATION",
        "days_sales_outstanding",
        Direction.UP,
        "signal.dso_deterioration",
        note="Permitted phrasing is that collection has lengthened. Any reading "
        "of intent requires evidence from the filing (section 42).",
    ),
    SignalRule(
        "SIG_INVENTORY_BUILD",
        "inventory_growth_gap",
        Direction.UP,
        "signal.inventory_build",
        note="Never promises a future write-down (section 42).",
    ),
    SignalRule(
        "SIG_RECEIVABLES_GROWTH_GAP",
        "receivables_growth_gap",
        Direction.UP,
        "signal.receivables_growth_gap",
    ),
    SignalRule(
        "SIG_DEBT_BUILD",
        "net_debt",
        Direction.UP,
        "signal.debt_build",
    ),
    SignalRule(
        "SIG_DILUTION",
        "dilution_yoy",
        Direction.UP,
        "signal.dilution",
    ),
)

ALL_RULES: Final[tuple[SignalRule, ...]] = (*CORE_RULES, *EXTENDED_RULES)
RULES_BY_CODE: Final[dict[str, SignalRule]] = {rule.code: rule for rule in ALL_RULES}
