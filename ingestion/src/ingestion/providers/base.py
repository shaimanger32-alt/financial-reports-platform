"""Provider abstraction.

The financial core must never learn a MAGNA or SEC URL (spec section 40). Every
provider is reduced to the same small vocabulary here, and everything
provider-specific stays behind this boundary.

Note on shape: spec section 40 proposes `list_filings` and `fetch_filing_facts`.
The MAGNA API has no filing-listing endpoint and no per-filing fact endpoint --
it is a fact query engine keyed by entity, concept, year and quarter. Filings are
*discovered* from the reference numbers attached to returned facts. The protocol
below therefore keeps the spec's intent (one canonical vocabulary, swappable
implementations) with a query shape that a fact-oriented source can actually
satisfy. SEC EDGAR fits it too: its companyfacts endpoint is also fact-oriented.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol, runtime_checkable

PeriodKind = Literal["instant", "duration"]


class ProviderError(RuntimeError):
    """Any failure attributable to the upstream provider."""


class ProviderUnavailableError(ProviderError):
    """The provider could not be reached, or did not answer in time."""


class ProviderNotSupportedError(ProviderError):
    """The provider cannot serve this capability at all."""


@dataclass(frozen=True, slots=True)
class ProviderEntity:
    """A reporting entity as the provider describes it."""

    provider_entity_id: str
    name: str
    name_en: str | None
    sector_code: str | None
    sector_name: str | None


@dataclass(frozen=True, slots=True)
class ProviderConcept:
    """A reportable concept in the provider's taxonomy, e.g. an XBRL tag."""

    name: str
    label: str | None

    @property
    def namespace(self) -> str | None:
        """Taxonomy prefix. `ifrs-full` is standard; anything else is an extension."""
        return self.name.split(":", 1)[0] if ":" in self.name else None

    @property
    def is_extension(self) -> bool:
        """True when the concept is company-specific rather than standard.

        Standard means a published taxonomy: `ifrs-full` for Israeli filers,
        `us-gaap` and `dei` for American ones. Anything else is an issuer
        extension, which decision 0010 declines to build analysis on.
        """
        return self.namespace not in (None, "ifrs-full", "us-gaap", "dei")


@dataclass(frozen=True, slots=True)
class ProviderPeriod:
    """A reporting period exactly as the provider expressed it.

    Semantic interpretation -- quarter versus year-to-date, which fiscal quarter
    a range belongs to -- is deliberately not decided here. That is domain logic
    and lands in financial_core in phase 2.
    """

    kind: PeriodKind
    end: date
    start: date | None = None
    raw: str = ""

    @property
    def days(self) -> int | None:
        """Length in days for a duration, else None."""
        if self.kind == "instant" or self.start is None:
            return None
        return (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True)
class ProviderFact:
    """One reported value, kept as close to the source as possible.

    `value` is None when the provider returned the row without a figure. That is
    an unknown, never a zero (spec section 4.4).
    """

    provider_entity_id: str
    provider_filing_id: str
    concept: str
    period: ProviderPeriod
    value: float | None
    unit: str | None
    scale: int | None
    decimals: int | None
    statement: str | None
    dimensions: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def is_dimensional(self) -> bool:
        """True when the fact is a breakdown rather than a consolidated total."""
        return bool(self.dimensions)


@dataclass(frozen=True, slots=True)
class FactQuery:
    """What to ask a provider for."""

    entity_ids: Sequence[str] = ()
    concepts: Sequence[str] = ()
    from_year: int = 0
    to_year: int = 0
    quarters: Sequence[str] = ("q1", "q2", "q3", "q4")


@dataclass(frozen=True, slots=True)
class FactBatch:
    """Facts plus the raw payload they came from.

    The raw payload travels with the parsed result so it can be archived and
    reprocessed later without calling the provider again (spec section 32,
    step 4).
    """

    facts: Sequence[ProviderFact]
    raw_payload: bytes
    content_hash: str
    retrieved_at: str
    source_reference: str


@runtime_checkable
class FinancialDataProvider(Protocol):
    """The only thing the rest of the system knows about a data source."""

    provider_code: str

    def list_entities(self) -> Sequence[ProviderEntity]:
        """Every entity the provider can report on."""
        ...

    def list_concepts(self) -> Sequence[ProviderConcept]:
        """Every concept in the provider's taxonomy."""
        ...

    def fetch_facts(self, query: FactQuery) -> FactBatch:
        """Retrieve facts matching the query, together with the raw payload."""
        ...

    def fetch_document(self, provider_filing_id: str) -> bytes:
        """Full filing document. Raises ProviderNotSupportedError when unavailable."""
        ...
