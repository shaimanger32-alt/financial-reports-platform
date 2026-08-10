"""Resolving a canonical metric from whichever concept an issuer happened to use.

Decision 0009: a metric maps to an ordered list of raw concepts. The first one
that a company actually reported wins, and the concept that won is recorded on
the resulting fact so the user can always see what the number really came from.

The algorithm is provider-agnostic. Which concepts sit in which chain is
provider knowledge and lives in `ingestion`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class ResolutionOutcome(StrEnum):
    """Why a resolution ended the way it did."""

    RESOLVED = "resolved"
    """A candidate concept carried a value."""

    NO_CANDIDATE_REPORTED = "no_candidate_reported"
    """The chain exists, but the company reported none of its concepts."""

    NO_MAPPING = "no_mapping"
    """No chain is defined for this metric at all."""


@dataclass(frozen=True, slots=True, order=True)
class ConceptCandidate:
    """One rung of a fallback chain.

    A candidate scoped to a company overrides the general chain for that company
    alone, which is how issuer extensions are handled without polluting the
    shared mapping.
    """

    priority: int
    raw_concept: str
    company_scoped: bool = False


@dataclass(frozen=True, slots=True)
class Resolution:
    """What the chain produced, and what it was based on."""

    metric_code: str
    outcome: ResolutionOutcome
    raw_concept: str | None = None
    value: float | None = None
    company_scoped: bool = False
    considered: tuple[str, ...] = ()

    @property
    def is_resolved(self) -> bool:
        return self.outcome is ResolutionOutcome.RESOLVED


def resolve_metric(
    metric_code: str,
    candidates: Sequence[ConceptCandidate],
    reported: Mapping[str, float | None],
) -> Resolution:
    """Pick the value for one metric, for one period.

    `reported` maps raw concept to the value the company reported for it, where
    `None` means the concept appeared without a figure. A concept with no value
    is not a match: the chain keeps looking rather than resolving to nothing.

    Company-scoped candidates are tried before the general chain regardless of
    priority. That is what makes an override an override.
    """
    if not candidates:
        return Resolution(metric_code=metric_code, outcome=ResolutionOutcome.NO_MAPPING)

    ordered = sorted(candidates, key=lambda c: (not c.company_scoped, c.priority, c.raw_concept))
    considered = tuple(candidate.raw_concept for candidate in ordered)

    for candidate in ordered:
        value = reported.get(candidate.raw_concept)
        if value is not None:
            return Resolution(
                metric_code=metric_code,
                outcome=ResolutionOutcome.RESOLVED,
                raw_concept=candidate.raw_concept,
                value=value,
                company_scoped=candidate.company_scoped,
                considered=considered,
            )

    return Resolution(
        metric_code=metric_code,
        outcome=ResolutionOutcome.NO_CANDIDATE_REPORTED,
        considered=considered,
    )


def resolve_all(
    chains: Mapping[str, Sequence[ConceptCandidate]],
    reported: Mapping[str, float | None],
) -> dict[str, Resolution]:
    """Resolve every metric that has a chain, for one period."""
    return {
        metric_code: resolve_metric(metric_code, candidates, reported)
        for metric_code, candidates in chains.items()
    }
