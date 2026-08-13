"""Data quality checks that run before anything is analysed (spec section 21).

`basics` is section 21.1: units, contradictory duplicates and values that cannot
exist. `identities` is section 21.2: the accounting equations. Restatements —
the part of 21.3 that is built — are found in the database layer, because they
are a fact about two filings rather than about one period's figures.
"""

from financial_core.validation.basics import (
    BASICS_VERSION,
    NON_NEGATIVE_METRICS,
    POSITIVE_METRICS,
    BasicFinding,
    BasicIssue,
    Observation,
    check_basics,
    check_contradictory_duplicates,
    check_impossible_values,
    check_unit_consistency,
)
from financial_core.validation.identities import (
    IdentityCheck,
    IdentityOutcome,
    check_all,
    check_balance_sheet,
    check_balance_sheet_total,
    check_cash_bridge,
    check_gross_profit,
    within_tolerance,
)

__all__ = [
    "BASICS_VERSION",
    "NON_NEGATIVE_METRICS",
    "POSITIVE_METRICS",
    "BasicFinding",
    "BasicIssue",
    "IdentityCheck",
    "IdentityOutcome",
    "Observation",
    "check_all",
    "check_balance_sheet",
    "check_balance_sheet_total",
    "check_basics",
    "check_cash_bridge",
    "check_contradictory_duplicates",
    "check_gross_profit",
    "check_impossible_values",
    "check_unit_consistency",
    "within_tolerance",
]
