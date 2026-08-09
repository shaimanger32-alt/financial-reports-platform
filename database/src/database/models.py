"""The canonical financial store.

Design notes worth keeping in view while reading:

* A period is a row, not a set of columns repeated on every table (decision
  0008). That is what stops the same quarter being recorded two incompatible
  ways in two places, which spec section 14.6 forbids.
* Money is `NUMERIC`, so nothing is lost in storage or in database-side
  aggregation (decision 0008).
* A fact records whether the issuer reported it or we derived it, and a derived
  fact links to the facts it came from (decision 0009).
* `raw_concept` is never discarded after normalisation (spec section 12).
* Restatement is not a silent overwrite. Both values survive, attached to the
  filings that carried them (spec section 11.2).

Only what phase 2 needs is defined here. Calculated metrics, signals, patterns,
evidence and snapshots arrive with the phases that build them.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from financial_core.periods import DurationKind, PeriodKind
from financial_core.provenance import ConsolidationScope, Origin, RecencySource
from financial_core.quality import QualityStatus

# Values are whole currency units up to roughly 1e12, with room for ratios and
# per-share figures below the point.
MONEY = Numeric(38, 6)


def _enum(python_enum: type, name: str) -> Enum:
    """A native PostgreSQL enum storing the member *values*, not their names."""
    return Enum(
        python_enum,
        name=name,
        native_enum=True,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )


class Company(Base):
    """A reporting entity.

    Identity is (provider, provider_entity_id) rather than a ticker: tickers
    change, and the same company may be reachable through several providers when
    the US source is added.
    """

    __tablename__ = "company"
    __table_args__ = (
        UniqueConstraint("provider", "provider_entity_id", name="uq_company_provider_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    provider: Mapped[str] = mapped_column(String(32))
    provider_entity_id: Mapped[str] = mapped_column(String(64))

    legal_name: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)

    ticker: Mapped[str | None] = mapped_column(String(32))
    security_number: Mapped[str | None] = mapped_column(String(32))
    registry_id: Mapped[str | None] = mapped_column(String(64))

    country: Mapped[str] = mapped_column(String(2), default="IL")
    sector_code: Mapped[str | None] = mapped_column(String(32))
    sector_name: Mapped[str | None] = mapped_column(Text)

    # Set by hand for the first companies. Spec section 6.2 explicitly does not
    # ask for an automatic classifier in the MVP.
    business_model: Mapped[str | None] = mapped_column(String(64))
    company_stage: Mapped[str | None] = mapped_column(String(32))

    reporting_currency: Mapped[str] = mapped_column(String(3), default="ILS")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    filings: Mapped[list["Filing"]] = relationship(back_populates="company")
    periods: Mapped[list["AnalysisPeriod"]] = relationship(back_populates="company")


class Filing(Base):
    """One report as published by the issuer.

    MAGNA exposes no filing list, so these rows are discovered from the
    reference numbers carried by facts (decision 0008), and no publication date
    is available (decision 0009).
    """

    __tablename__ = "filing"
    __table_args__ = (
        UniqueConstraint("provider", "provider_filing_id", name="uq_filing_provider_id"),
        Index("ix_filing_company_recency", "company_id", "recency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))

    provider: Mapped[str] = mapped_column(String(32))
    provider_filing_id: Mapped[str] = mapped_column(String(64))

    report_type: Mapped[str | None] = mapped_column(String(32))
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recency_source: Mapped[RecencySource] = mapped_column(
        _enum(RecencySource, "recency_source"), default=RecencySource.UNKNOWN
    )
    recency_key: Mapped[str] = mapped_column(
        String(64),
        doc=(
            "Sortable ordering key. Derived from the reference number when the "
            "provider gives no publication date; provisional by construction."
        ),
    )

    source_url: Mapped[str | None] = mapped_column(Text)
    document_url: Mapped[str | None] = mapped_column(Text)
    source_format: Mapped[str] = mapped_column(String(16), default="ixbrl")
    content_hash: Mapped[str | None] = mapped_column(String(64))

    is_restatement: Mapped[bool] = mapped_column(Boolean, default=False)
    supersedes_filing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("filing.id", ondelete="SET NULL")
    )

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="filings")


class AnalysisPeriod(Base):
    """A period the system is prepared to reason about.

    Defined once and referenced everywhere, so a quarter cannot be recorded as a
    quarter in one table and as a year-to-date window in another. The check
    constraints mirror `FiscalPeriod.__post_init__`, so the rule holds even for
    a row written outside the application.
    """

    __tablename__ = "analysis_period"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_period_company_code"),
        CheckConstraint("fiscal_quarter BETWEEN 1 AND 4", name="ck_period_quarter_range"),
        CheckConstraint(
            "(period_kind = 'instant' AND duration_kind IS NULL AND period_start IS NULL)"
            " OR (period_kind = 'duration' AND duration_kind IS NOT NULL"
            " AND period_start IS NOT NULL AND period_start <= period_end)",
            name="ck_period_kind_coherent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))

    code: Mapped[str] = mapped_column(String(32), doc="e.g. 2024-Q3, 2024-YTD-Q2, 2024-FY")
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_quarter: Mapped[int] = mapped_column(Integer)
    period_kind: Mapped[PeriodKind] = mapped_column(_enum(PeriodKind, "period_kind"))
    duration_kind: Mapped[DurationKind | None] = mapped_column(_enum(DurationKind, "duration_kind"))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="periods")


class MetricDefinition(Base):
    """A canonical metric, independent of any provider's vocabulary.

    Codes are English (spec section 45) so that adding the US market needs no
    schema migration; display names are localised.
    """

    __tablename__ = "metric_definition"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)

    display_name_he: Mapped[str] = mapped_column(Text)
    display_name_en: Mapped[str] = mapped_column(Text)
    description_he: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)

    category: Mapped[str] = mapped_column(String(32))
    metric_type: Mapped[str] = mapped_column(String(16), doc="reported | derived")
    unit_type: Mapped[str] = mapped_column(String(16), doc="currency | ratio | days | count")
    formula_version: Mapped[str | None] = mapped_column(String(16))
    sector_scope: Mapped[str] = mapped_column(String(32), default="general")
    is_core: Mapped[bool] = mapped_column(Boolean, default=True)


class ConceptMapping(Base):
    """Raw provider concept to canonical metric.

    `priority` implements the ordered fallback chain from decision 0009: the
    lowest priority that resolves for a company wins. A row with `company_id`
    set overrides the general chain for that company only, which is how issuer
    extensions are handled without polluting the shared mapping.

    Mappings are versioned data rather than code (spec section 33), so a change
    to the chain does not silently rewrite the meaning of past analyses.
    """

    __tablename__ = "concept_mapping"
    __table_args__ = (
        # NULLS NOT DISTINCT is essential, not decorative. `company_id` is NULL
        # for the general chain, which is the common case, and under the default
        # SQL rule two NULLs are unequal -- so the constraint would permit exactly
        # the duplicates it exists to prevent.
        UniqueConstraint(
            "provider",
            "raw_concept",
            "company_id",
            "mapping_version",
            name="uq_mapping_concept_scope_version",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_mapping_lookup", "provider", "metric_code", "priority"),
        CheckConstraint("priority >= 0", name="ck_mapping_priority_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    provider: Mapped[str] = mapped_column(String(32))
    taxonomy: Mapped[str | None] = mapped_column(String(32), doc="namespace, e.g. ifrs-full")
    raw_concept: Mapped[str] = mapped_column(String(256))
    metric_code: Mapped[str] = mapped_column(
        ForeignKey("metric_definition.code", ondelete="CASCADE")
    )

    priority: Mapped[int] = mapped_column(Integer, default=0, doc="lower wins")
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"),
        doc="set only for a company-specific override",
    )

    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    mapping_version: Mapped[str] = mapped_column(String(16), default="v1")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancialFact(Base):
    """One value, for one concept, for one period, from one filing.

    The uniqueness constraint is what makes re-ingestion idempotent (spec
    section 33): the same fact from the same filing cannot land twice. It
    deliberately does *not* span filings, because the same concept and period
    reported differently by two filings is a restatement, and both sides of a
    restatement must survive.
    """

    __tablename__ = "financial_fact"
    __table_args__ = (
        UniqueConstraint(
            "filing_id",
            "raw_concept",
            "period_id",
            "dimensions_hash",
            "origin",
            name="uq_fact_identity",
        ),
        Index("ix_fact_company_metric_period", "company_id", "metric_code", "period_id"),
        Index("ix_fact_company_concept_period", "company_id", "raw_concept", "period_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("company.id", ondelete="CASCADE"))
    filing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("filing.id", ondelete="CASCADE"))
    period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_period.id", ondelete="RESTRICT")
    )

    origin: Mapped[Origin] = mapped_column(_enum(Origin, "fact_origin"), default=Origin.REPORTED)

    raw_concept: Mapped[str] = mapped_column(String(256), doc="never discarded after normalisation")
    metric_code: Mapped[str | None] = mapped_column(
        ForeignKey("metric_definition.code", ondelete="SET NULL")
    )

    # Null means unknown. It is never zero (spec section 4.4).
    value: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str | None] = mapped_column(String(3))
    unit: Mapped[str | None] = mapped_column(String(32))
    scale: Mapped[int | None] = mapped_column(Integer)
    decimals: Mapped[int | None] = mapped_column(Integer)

    statement: Mapped[str | None] = mapped_column(Text, doc="which statement the value came from")
    consolidation_scope: Mapped[ConsolidationScope] = mapped_column(
        _enum(ConsolidationScope, "consolidation_scope"), default=ConsolidationScope.UNKNOWN
    )
    segment: Mapped[str | None] = mapped_column(Text)
    geography: Mapped[str | None] = mapped_column(Text)
    dimensions_json: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    dimensions_hash: Mapped[str] = mapped_column(
        String(64),
        default="",
        doc="stable hash of dimensions_json; empty string for a consolidated total",
    )

    source_location: Mapped[str | None] = mapped_column(Text)
    source_text: Mapped[str | None] = mapped_column(Text)

    quality_status: Mapped[QualityStatus] = mapped_column(
        _enum(QualityStatus, "quality_status"), default=QualityStatus.VERIFIED
    )
    derivation_formula: Mapped[str | None] = mapped_column(
        Text, doc="human-readable rule, set only when origin is derived"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    derived_from: Mapped[list["FactDerivation"]] = relationship(
        back_populates="derived_fact",
        foreign_keys="FactDerivation.derived_fact_id",
        cascade="all, delete-orphan",
    )


class FactDerivation(Base):
    """Lineage of a derived fact.

    `Q4 = FY - 9M` becomes two rows here, so the figure can be traced back to
    the reported values behind it (spec section 4.2, decision 0009).
    """

    __tablename__ = "fact_derivation"
    __table_args__ = (
        UniqueConstraint("derived_fact_id", "ordinal", name="uq_derivation_ordinal"),
        CheckConstraint("derived_fact_id <> input_fact_id", name="ck_derivation_not_self"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    derived_fact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("financial_fact.id", ondelete="CASCADE")
    )
    input_fact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("financial_fact.id", ondelete="RESTRICT")
    )

    role: Mapped[str] = mapped_column(String(16), doc="minuend | subtrahend | addend")
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    derived_fact: Mapped[FinancialFact] = relationship(
        back_populates="derived_from", foreign_keys=[derived_fact_id]
    )
    input_fact: Mapped[FinancialFact] = relationship(foreign_keys=[input_fact_id])
