"""What a pattern is, and what it is not.

Spec section 16: a pattern is a **combination of signals**, and nothing more. It
joins observations that are already true into one thing worth reading, and it
does not add a reason for them. "The gap between accounting profit and cash
widened, seen from two directions" is a pattern; "the company is managing its
earnings" is not, and combining two numbers has not earned the second sentence.

Section 42 is what makes that boundary hold: a pattern carries a `message_key`
and never a sentence, so no engine can assert a cause. A cause needs an explicit
quote from the filing, which is the evidence engine's work in phase 6.

Section 20 sets confidence. Two independent signals pointing the same way is
`MEDIUM`. `HIGH` requires an explanation from the filing itself, so this engine
cannot issue it — see `Confidence` in `financial_core.signals.model`.
"""

from dataclasses import dataclass
from enum import StrEnum

from financial_core.periods import FiscalPeriod
from financial_core.signals.model import Confidence, Severity


class ExplanationStatus(StrEnum):
    """Whether the filing was searched for an explanation, and what was found.

    Spec section 11.7. Everything this engine produces is `NOT_SEARCHED`: the
    evidence engine arrives in phase 6, and until it does, the honest value is
    "nobody has looked" rather than "nothing was found".
    """

    NOT_SEARCHED = "not_searched"
    NO_EVIDENCE = "no_evidence"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class Pattern:
    """Several observations about one company in one period, read together."""

    code: str
    period: FiscalPeriod
    signal_codes: tuple[str, ...]
    """The signals that actually matched, in the order the rule lists them.
    This is the whole basis of the pattern; there is nothing else behind it."""
    severity: Severity
    confidence: Confidence
    rule_version: str
    message_key: str = ""
    """Key into the localised phrasing. The wording never lives in the engine
    (spec section 42)."""
    explanation_status: ExplanationStatus = ExplanationStatus.NOT_SEARCHED
    optional_signal_codes: tuple[str, ...] = ()
    """Matched signals that corroborate the pattern without being required. Kept
    apart from the required ones so a reader can tell what carried it."""
    independent_signal_count: int = 0
    """How many of the matched signals are independent observations rather than
    the same arithmetic seen twice. This is what confidence rests on, not the
    raw count."""
    dependent_signals_counted_once: tuple[str, ...] = ()
    """Groups of matched signals that share their inputs, recorded so the payload
    can distinguish corroboration from restatement."""

    @property
    def all_signal_codes(self) -> tuple[str, ...]:
        return (*self.signal_codes, *self.optional_signal_codes)

    @property
    def is_concerning(self) -> bool:
        return self.severity.is_concerning
