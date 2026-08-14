"""Report memory: what a pattern asks the next report to answer.

Spec section 28. A watch item is the only thing in the product that persists an
observation across periods, so it is deliberately narrow — it re-reads one
metric and says whether the move widened, narrowed or stopped. It never
predicts, never advises, and never closes itself because the data went missing.
"""

from financial_core.watch.engine import MESSAGE_KEYS, open_items, review
from financial_core.watch.model import WatchItem, WatchObservation, WatchStatus

WATCH_VERSION = "v1"

__all__ = [
    "MESSAGE_KEYS",
    "WATCH_VERSION",
    "WatchItem",
    "WatchObservation",
    "WatchStatus",
    "open_items",
    "review",
]
