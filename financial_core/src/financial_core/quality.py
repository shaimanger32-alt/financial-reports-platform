"""Data quality states.

Spec section 21.4 defines the vocabulary; section 21 defines when each applies.
The rule that matters most: no high-confidence analysis may be produced from
data marked `NOT_COMPARABLE`.
"""

from enum import StrEnum


class QualityStatus(StrEnum):
    """How much analytical weight a figure can carry."""

    VERIFIED = "verified"
    """Passed validation with no warning."""

    USABLE_WITH_WARNING = "usable_with_warning"
    """Usable, but something about it needs stating alongside."""

    INCOMPLETE = "incomplete"
    """A required input is missing. Not an error, and not a zero."""

    NOT_COMPARABLE = "not_comparable"
    """A restatement, standard change, acquisition or currency change breaks
    comparison with other periods."""

    REJECTED = "rejected"
    """Failed validation outright. Never used in analysis."""

    @property
    def is_analysable(self) -> bool:
        """Whether the metric engine may consume a figure in this state."""
        return self in {QualityStatus.VERIFIED, QualityStatus.USABLE_WITH_WARNING}

    @property
    def supports_high_confidence(self) -> bool:
        """Whether a finding built on this figure may claim high confidence."""
        return self is QualityStatus.VERIFIED
