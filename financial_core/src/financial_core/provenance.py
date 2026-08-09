"""Where a value came from, and how much of that we actually know.

Spec section 4.3 requires the system to distinguish what was reported from what
was computed. Decision 0009 extends that: when both exist for the same period,
both are kept and neither hides the other.
"""

from enum import StrEnum


class Origin(StrEnum):
    """Whether a stored figure came from the issuer or from us."""

    REPORTED = "reported"
    """Appeared in a filing exactly as stored."""

    DERIVED = "derived"
    """Computed by us from reported figures, with its inputs recorded."""


class ConsolidationScope(StrEnum):
    """Which set of books a figure belongs to.

    Spec section 21.3 treats a consolidated/separate mismatch as a comparability
    break, so the scope has to travel with the fact rather than be assumed.
    """

    CONSOLIDATED = "consolidated"
    SEPARATE = "separate"
    UNKNOWN = "unknown"


class RecencySource(StrEnum):
    """How we know when a filing was published.

    MAGNA supplies no publication date. Decision 0009 permits inferring order
    from the reference number, on condition that the inference is labelled as
    one and never presented as a fact the source provided.
    """

    PROVIDER = "provider"
    """The provider gave us a real publication date."""

    INFERRED = "inferred"
    """Ordering deduced from the filing reference. Provisional."""

    UNKNOWN = "unknown"
    """Neither available. The user is told the source did not supply it."""
