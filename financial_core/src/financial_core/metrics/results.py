"""What a calculation returns.

A result is never a bare number. It carries the formula version that produced
it, the inputs it consumed, and a warning when the figure needs one -- which is
what makes an insight traceable back to the facts (spec sections 4.2 and 33).

`value is None` is a first-class outcome. Spec section 0, rule 5: where
correctness is uncertain, return null with a warning rather than guess.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from financial_core.metrics.catalogue import UnitType
from financial_core.periods import FiscalPeriod
from financial_core.quality import QualityStatus


class MetricWarning(StrEnum):
    """Why a figure is missing, or why it needs reading with care."""

    MISSING_INPUT = "missing_input"
    """An input was not reported. Not an error, and not a zero."""

    NON_POSITIVE_BASE = "non_positive_base"
    """A growth rate was asked for against a base at or below zero, where a
    percentage is meaningless (spec section 13.1). The absolute change and the
    direction of the crossing are in `detail`."""

    IMMATERIAL_DENOMINATOR = "immaterial_denominator"
    """The denominator is too small for the ratio to mean anything."""

    NEGATIVE_DENOMINATOR = "negative_denominator"
    """A ratio whose denominator is negative would invert its sign and read as
    the opposite of what it is."""

    DERIVED_INPUT = "derived_input"
    """At least one input was derived by us rather than reported."""

    CROSSED_ZERO = "crossed_zero"
    """The figure moved between loss and profit, which a percentage hides."""

    SINGLE_PERIOD = "single_period"
    """Only one period was available where a comparison needs two."""


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One metric, for one period."""

    code: str
    period: FiscalPeriod
    value: float | None
    unit_type: UnitType
    formula_version: str
    inputs: dict[str, float | None] = field(default_factory=dict)
    detail: dict[str, float] = field(default_factory=dict)
    warnings: tuple[MetricWarning, ...] = ()
    quality: QualityStatus = QualityStatus.VERIFIED

    @property
    def is_available(self) -> bool:
        return self.value is not None

    @property
    def missing_inputs(self) -> tuple[str, ...]:
        """Which inputs were unknown, for explaining a null to a reader."""
        return tuple(name for name, value in self.inputs.items() if value is None)

    def with_warning(self, warning: MetricWarning) -> "MetricResult":
        if warning in self.warnings:
            return self
        return MetricResult(
            code=self.code,
            period=self.period,
            value=self.value,
            unit_type=self.unit_type,
            formula_version=self.formula_version,
            inputs=self.inputs,
            detail=self.detail,
            warnings=(*self.warnings, warning),
            quality=self.quality,
        )
