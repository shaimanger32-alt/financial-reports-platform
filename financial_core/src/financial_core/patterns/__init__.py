"""The pattern engine.

A pattern is a combination of signals (spec section 16). It is never a cause and
never an intention: grouping observations does not license a sentence about why
they happened, which needs an explicit quote from the filing (section 42).
"""

from financial_core.patterns.engine import evaluate_all, evaluate_pattern
from financial_core.patterns.model import ExplanationStatus, Pattern
from financial_core.patterns.rules import (
    ALL_PATTERNS,
    CORE_PATTERNS,
    EXTENDED_PATTERNS,
    PATTERN_VERSION,
    PATTERNS_BY_CODE,
    Comparison,
    MetricCondition,
    PatternRule,
)

__all__ = [
    "ALL_PATTERNS",
    "CORE_PATTERNS",
    "EXTENDED_PATTERNS",
    "PATTERNS_BY_CODE",
    "PATTERN_VERSION",
    "Comparison",
    "ExplanationStatus",
    "MetricCondition",
    "Pattern",
    "PatternRule",
    "evaluate_all",
    "evaluate_pattern",
]
