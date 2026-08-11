"""The floors below which a movement is not worth a sentence.

Version 1. Every number here is a judgement, which is why it is data with a
version rather than a constant inside a rule.

## What these are, and are not

The company's own history decides whether a move is *unusual*. These decide
whether it is *worth mentioning at all*. Both bars have to be cleared.

The floor exists because statistical unusualness and financial relevance are
different things. A company whose collection period has sat at exactly 50.0 days
for three years moves to 50.4, and that is infinitely many robust units from its
norm while remaining a rounding artefact. Without a floor the engine would
report it with a straight face.

## How each number was chosen

The principle is: **the smallest move a careful reader would still describe out
loud.** Not the smallest detectable move, and not one calibrated to produce a
pleasing number of signals.

* **5 days** for collection, inventory and payment periods. Under a week is
  inside the noise of when invoices happen to clear at a quarter end.
* **1.0 percentage point** for margins. Below that, presentation changes and
  mix effects explain more than performance does.
* **0.10** for the current and quick ratios. A tenth is the smallest step at
  which the usual rules of thumb about these ratios change their reading.
* **0.25** for leverage. The same reasoning, on a measure that ranges wider.
* **5 percentage points** for equity ratio and growth rates. A twentieth of the
  balance sheet, or of a growth rate, is a real shift in either.
* **0.15** for cash conversion. Profit converting to cash at 0.85 rather than
  1.00 is worth saying; at 0.98 it is not.
* **2 percentage points** for the accruals proxy, which is scaled by assets and
  therefore moves in small numbers.

None of these is calibrated against a peer distribution, because there is not
yet enough coverage to build one. Spec section 17 puts peer medians last for
that reason, and this file is where they will enter when there are.
"""

from typing import Final

from financial_core.signals.model import Severity
from financial_core.signals.thresholds import Threshold, ThresholdSet

DEFAULT_THRESHOLD_VERSION: Final[str] = "v1"

# How far from the company's own norm a move must sit. Roughly: two robust units
# is a move outside the company's usual range, three is well outside it.
_UNUSUAL: Final[float] = 2.0
_VERY_UNUSUAL: Final[float] = 3.0

DEFAULT_THRESHOLDS: Final[ThresholdSet] = ThresholdSet(
    (
        # -- core: these fire for every company ---------------------------
        Threshold(
            "current_ratio",
            deviation=_UNUSUAL,
            minimum_magnitude=0.10,
            severity=Severity.WATCH,
        ),
        Threshold(
            "quick_ratio",
            deviation=_UNUSUAL,
            minimum_magnitude=0.10,
            severity=Severity.WATCH,
        ),
        Threshold(
            "liabilities_to_equity",
            deviation=_UNUSUAL,
            minimum_magnitude=0.25,
            severity=Severity.WATCH,
        ),
        Threshold(
            "equity_ratio",
            deviation=_UNUSUAL,
            minimum_magnitude=0.05,
            severity=Severity.WATCH,
        ),
        Threshold(
            "cash_conversion",
            deviation=_UNUSUAL,
            minimum_magnitude=0.15,
            severity=Severity.WATCH,
        ),
        Threshold(
            "accruals_proxy",
            deviation=_UNUSUAL,
            minimum_magnitude=0.02,
            severity=Severity.WATCH,
        ),
        Threshold(
            "operating_cash_flow_growth_yoy",
            deviation=_UNUSUAL,
            minimum_magnitude=0.05,
            severity=Severity.WATCH,
        ),
        Threshold(
            "net_income_growth_yoy",
            deviation=_UNUSUAL,
            minimum_magnitude=0.05,
            severity=Severity.INFO,
        ),
        Threshold(
            "effective_tax_rate",
            deviation=_VERY_UNUSUAL,
            minimum_magnitude=0.05,
            severity=Severity.INFO,
        ),
        # -- extended: silent where the metric is null --------------------
        Threshold(
            "days_sales_outstanding",
            deviation=_UNUSUAL,
            minimum_magnitude=5.0,
            severity=Severity.WATCH,
        ),
        Threshold(
            "days_inventory_outstanding",
            deviation=_UNUSUAL,
            minimum_magnitude=5.0,
            severity=Severity.WATCH,
        ),
        Threshold(
            "gross_margin",
            deviation=_UNUSUAL,
            minimum_magnitude=0.01,
            severity=Severity.WATCH,
        ),
        Threshold(
            "operating_margin",
            deviation=_UNUSUAL,
            minimum_magnitude=0.01,
            severity=Severity.INFO,
        ),
        Threshold(
            "revenue_growth_yoy",
            deviation=_UNUSUAL,
            minimum_magnitude=0.05,
            severity=Severity.INFO,
        ),
        Threshold(
            "inventory_growth_gap",
            deviation=_UNUSUAL,
            minimum_magnitude=5.0,
            severity=Severity.WATCH,
        ),
        Threshold(
            "receivables_growth_gap",
            deviation=_UNUSUAL,
            minimum_magnitude=5.0,
            severity=Severity.WATCH,
        ),
        Threshold(
            "net_debt",
            deviation=_UNUSUAL,
            minimum_magnitude=0.0,
            severity=Severity.WATCH,
        ),
        Threshold(
            "dilution_yoy",
            deviation=_UNUSUAL,
            minimum_magnitude=0.02,
            severity=Severity.WATCH,
        ),
    ),
    version=DEFAULT_THRESHOLD_VERSION,
)
