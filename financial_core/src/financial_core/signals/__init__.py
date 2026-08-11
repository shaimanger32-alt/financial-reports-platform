"""The signal engine.

A signal is an observation about numbers. It is never a cause, never an
intention and never an accusation (spec sections 15 and 42).
"""

from financial_core.signals.baseline import Baseline, build_baseline, consecutive_run
from financial_core.signals.defaults import DEFAULT_THRESHOLD_VERSION, DEFAULT_THRESHOLDS
from financial_core.signals.engine import (
    MetricObservation,
    MetricSeries,
    evaluate_all,
    evaluate_rule,
)
from financial_core.signals.model import Confidence, Direction, Severity, Signal
from financial_core.signals.rules import (
    ALL_RULES,
    CORE_RULES,
    EXTENDED_RULES,
    RULES_BY_CODE,
    SignalRule,
)
from financial_core.signals.thresholds import THRESHOLD_VERSION, Threshold, ThresholdSet

__all__ = [
    "ALL_RULES",
    "CORE_RULES",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_THRESHOLD_VERSION",
    "EXTENDED_RULES",
    "RULES_BY_CODE",
    "THRESHOLD_VERSION",
    "Baseline",
    "Confidence",
    "Direction",
    "MetricObservation",
    "MetricSeries",
    "Severity",
    "Signal",
    "SignalRule",
    "Threshold",
    "ThresholdSet",
    "build_baseline",
    "consecutive_run",
    "evaluate_all",
    "evaluate_rule",
]
