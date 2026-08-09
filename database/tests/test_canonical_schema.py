"""The canonical schema, and the rules it enforces in the database itself.

Application code can forget an invariant. A constraint cannot. Everything tested
here is a rule the spec states in prose and this schema turns into something the
database refuses to violate.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from database.models import (
    AnalysisPeriod,
    Company,
    ConceptMapping,
    FactDerivation,
    Filing,
    FinancialFact,
    MetricDefinition,
)
from financial_core.periods import DurationKind, PeriodKind
from financial_core.provenance import ConsolidationScope, Origin, RecencySource
from financial_core.quality import QualityStatus

pytestmark = pytest.mark.integration


def make_company(session: Session, entity_id: str = "520039413") -> Company:
    company = Company(
        provider="magna_xbrl",
        provider_entity_id=entity_id,
        legal_name='מטריקס אי.טי. בע"מ',
        display_name="Matrix IT",
        name_en="MATRIX IT LTD",
        sector_code="8800",
        sector_name="טכנולוגיה",
    )
    session.add(company)
    session.flush()
    return company


def make_filing(session: Session, company: Company, reference: str) -> Filing:
    filing = Filing(
        company_id=company.id,
        provider="magna_xbrl",
        provider_filing_id=reference,
        recency_key=reference,
        recency_source=RecencySource.INFERRED,
    )
    session.add(filing)
    session.flush()
    return filing


def make_period(
    session: Session,
    company: Company,
    code: str,
    *,
    year: int = 2023,
    quarter: int = 3,
    kind: PeriodKind = PeriodKind.DURATION,
    duration_kind: DurationKind | None = DurationKind.QUARTER,
    start: date | None = date(2023, 7, 1),
    end: date = date(2023, 9, 30),
) -> AnalysisPeriod:
    period = AnalysisPeriod(
        company_id=company.id,
        code=code,
        fiscal_year=year,
        fiscal_quarter=quarter,
        period_kind=kind,
        duration_kind=duration_kind,
        period_start=start,
        period_end=end,
    )
    session.add(period)
    session.flush()
    return period


def make_fact(
    session: Session,
    company: Company,
    filing: Filing,
    period: AnalysisPeriod,
    *,
    concept: str = "ifrs-full:Revenue",
    value: Decimal | None = Decimal("1333520000"),
    origin: Origin = Origin.REPORTED,
    dimensions_hash: str = "",
) -> FinancialFact:
    fact = FinancialFact(
        company_id=company.id,
        filing_id=filing.id,
        period_id=period.id,
        origin=origin,
        raw_concept=concept,
        value=value,
        currency="ILS",
        unit="ILS",
        scale=3,
        decimals=-3,
        consolidation_scope=ConsolidationScope.CONSOLIDATED,
        dimensions_hash=dimensions_hash,
    )
    session.add(fact)
    session.flush()
    return fact


# -- round trip -----------------------------------------------------------


def test_a_fact_round_trips_with_its_context(session: Session) -> None:
    company = make_company(session)
    filing = make_filing(session, company, "2023-01-104698")
    period = make_period(session, company, "2023-Q3")
    fact = make_fact(session, company, filing, period)

    session.expire_all()
    stored = session.get(FinancialFact, fact.id)

    assert stored is not None
    assert stored.value == Decimal("1333520000")
    assert stored.origin is Origin.REPORTED
    assert stored.quality_status is QualityStatus.VERIFIED
    assert stored.consolidation_scope is ConsolidationScope.CONSOLIDATED


def test_money_survives_the_round_trip_without_precision_loss(session: Session) -> None:
    """NUMERIC, not float. Nothing is lost in storage or in aggregation."""
    company = make_company(session)
    filing = make_filing(session, company, "2025-01-017214")
    period = make_period(session, company, "2024-FY")

    exact = Decimal("5579538000.123456")
    fact = make_fact(session, company, filing, period, value=exact)

    session.expire_all()
    stored = session.get(FinancialFact, fact.id)

    assert stored is not None
    assert stored.value == exact


def test_a_missing_value_is_null_and_not_zero(session: Session) -> None:
    """Spec section 4.4. The database must be able to hold 'unknown'."""
    company = make_company(session)
    filing = make_filing(session, company, "2023-01-104698")
    period = make_period(session, company, "2023-Q3")

    fact = make_fact(session, company, filing, period, value=None)

    session.expire_all()
    stored = session.get(FinancialFact, fact.id)

    assert stored is not None
    assert stored.value is None
    assert stored.value != Decimal(0)


# -- the period rules -----------------------------------------------------


def test_an_instant_may_not_carry_a_duration_kind(session: Session) -> None:
    """A balance date is not a window. The database refuses the contradiction."""
    company = make_company(session)

    with pytest.raises(IntegrityError, match="ck_period_kind_coherent"):
        make_period(
            session,
            company,
            "2023-Q3-instant",
            kind=PeriodKind.INSTANT,
            duration_kind=DurationKind.QUARTER,
            start=None,
        )


def test_a_duration_needs_a_start(session: Session) -> None:
    company = make_company(session)

    with pytest.raises(IntegrityError, match="ck_period_kind_coherent"):
        make_period(session, company, "2023-Q3-broken", start=None)


def test_a_duration_may_not_end_before_it_starts(session: Session) -> None:
    company = make_company(session)

    with pytest.raises(IntegrityError, match="ck_period_kind_coherent"):
        make_period(
            session,
            company,
            "2023-Q3-reversed",
            start=date(2023, 9, 30),
            end=date(2023, 7, 1),
        )


def test_quarter_must_be_between_one_and_four(session: Session) -> None:
    company = make_company(session)

    with pytest.raises(IntegrityError, match="ck_period_quarter_range"):
        make_period(session, company, "2023-Q7", quarter=7)


def test_a_period_code_is_unique_per_company(session: Session) -> None:
    """One quarter, one row. This is what stops the same period being recorded
    two incompatible ways (spec section 14.6)."""
    company = make_company(session)
    make_period(session, company, "2023-Q3")

    with pytest.raises(IntegrityError, match="uq_period_company_code"):
        make_period(session, company, "2023-Q3")


def test_the_same_code_is_allowed_for_a_different_company(session: Session) -> None:
    first = make_company(session, "520039413")
    second = make_company(session, "520039942")

    make_period(session, first, "2023-Q3")
    make_period(session, second, "2023-Q3")

    assert session.query(AnalysisPeriod).count() == 2


# -- idempotency and restatement -----------------------------------------


def test_the_same_fact_cannot_be_ingested_twice(session: Session) -> None:
    """Spec section 33: re-running ingestion must not create duplicates."""
    company = make_company(session)
    filing = make_filing(session, company, "2023-01-104698")
    period = make_period(session, company, "2023-Q3")

    make_fact(session, company, filing, period)

    with pytest.raises(IntegrityError, match="uq_fact_identity"):
        make_fact(session, company, filing, period)


def test_two_filings_may_disagree_about_the_same_period(session: Session) -> None:
    """A restatement is not an overwrite. Both values survive, each attached to
    the filing that carried it (spec section 11.2).

    These are Matrix IT's actual restated total assets.
    """
    company = make_company(session)
    period = make_period(
        session,
        company,
        "2023-Q3-instant",
        kind=PeriodKind.INSTANT,
        duration_kind=None,
        start=None,
    )
    earlier = make_filing(session, company, "2023-01-104698")
    later = make_filing(session, company, "2024-01-616266")

    make_fact(
        session,
        company,
        earlier,
        period,
        concept="ifrs-full:Assets",
        value=Decimal("3928894000"),
    )
    make_fact(
        session,
        company,
        later,
        period,
        concept="ifrs-full:Assets",
        value=Decimal("3882556000"),
    )

    values = {
        fact.value
        for fact in session.query(FinancialFact).filter_by(raw_concept="ifrs-full:Assets")
    }
    assert values == {Decimal("3928894000"), Decimal("3882556000")}


def test_reported_and_derived_coexist_for_one_period(session: Session) -> None:
    """Decision 0009: our figure never displaces the issuer's."""
    company = make_company(session)
    filing = make_filing(session, company, "2023-01-104698")
    period = make_period(session, company, "2023-Q3")

    make_fact(session, company, filing, period, origin=Origin.REPORTED)
    make_fact(session, company, filing, period, origin=Origin.DERIVED)

    origins = {fact.origin for fact in session.query(FinancialFact).all()}
    assert origins == {Origin.REPORTED, Origin.DERIVED}


def test_a_dimensional_breakdown_does_not_collide_with_the_total(session: Session) -> None:
    company = make_company(session)
    filing = make_filing(session, company, "2023-01-104698")
    period = make_period(session, company, "2023-Q3")

    make_fact(session, company, filing, period, dimensions_hash="")
    make_fact(session, company, filing, period, dimensions_hash="a1b2c3")

    assert session.query(FinancialFact).count() == 2


# -- lineage --------------------------------------------------------------


def test_a_derived_fact_records_where_it_came_from(session: Session) -> None:
    """Q4 = FY - 9M, traceable to both inputs (spec section 4.2)."""
    company = make_company(session)
    filing = make_filing(session, company, "2025-01-017214")

    annual = make_period(session, company, "2024-FY", year=2024, quarter=4)
    nine_months = make_period(session, company, "2024-YTD-Q3", year=2024, quarter=3)
    fourth_quarter = make_period(session, company, "2024-Q4", year=2024, quarter=4)

    annual_fact = make_fact(session, company, filing, annual, value=Decimal("5579538000"))
    nine_month_fact = make_fact(session, company, filing, nine_months, value=Decimal("4205255000"))

    derived = make_fact(
        session,
        company,
        filing,
        fourth_quarter,
        value=Decimal("1374283000"),
        origin=Origin.DERIVED,
    )
    derived.derivation_formula = "Q4 = 2024-FY - 2024-YTD-Q3"
    session.add_all(
        [
            FactDerivation(
                derived_fact_id=derived.id,
                input_fact_id=annual_fact.id,
                role="minuend",
                ordinal=0,
            ),
            FactDerivation(
                derived_fact_id=derived.id,
                input_fact_id=nine_month_fact.id,
                role="subtrahend",
                ordinal=1,
            ),
        ]
    )
    session.flush()
    session.expire_all()

    stored = session.get(FinancialFact, derived.id)
    assert stored is not None
    lineage = sorted(stored.derived_from, key=lambda link: link.ordinal)

    assert [link.role for link in lineage] == ["minuend", "subtrahend"]
    assert lineage[0].input_fact.value - lineage[1].input_fact.value == stored.value


def test_a_fact_cannot_be_derived_from_itself(session: Session) -> None:
    company = make_company(session)
    filing = make_filing(session, company, "2025-01-017214")
    period = make_period(session, company, "2024-Q4", year=2024, quarter=4)
    fact = make_fact(session, company, filing, period, origin=Origin.DERIVED)

    session.add(
        FactDerivation(derived_fact_id=fact.id, input_fact_id=fact.id, role="minuend", ordinal=0)
    )

    with pytest.raises(IntegrityError, match="ck_derivation_not_self"):
        session.flush()


# -- normalisation mapping ------------------------------------------------


def test_the_fallback_chain_is_ordered(session: Session) -> None:
    """Decision 0009: several raw concepts resolve to one metric, lowest
    priority first. This is what rescues DSO across companies that tag
    receivables differently."""
    session.add(
        MetricDefinition(
            code="trade_receivables",
            display_name_he="לקוחות",
            display_name_en="Trade receivables",
            category="working_capital",
            metric_type="reported",
            unit_type="currency",
        )
    )
    session.flush()

    chain = [
        "ifrs-full:TradeAndOtherCurrentReceivables",
        "ifrs-full:CurrentTradeReceivables",
        "ifrs-full:TradeReceivables",
    ]
    session.add_all(
        ConceptMapping(
            provider="magna_xbrl",
            taxonomy="ifrs-full",
            raw_concept=concept,
            metric_code="trade_receivables",
            priority=index,
        )
        for index, concept in enumerate(chain)
    )
    session.flush()

    resolved = (
        session.query(ConceptMapping)
        .filter_by(metric_code="trade_receivables", company_id=None)
        .order_by(ConceptMapping.priority)
        .all()
    )

    assert [mapping.raw_concept for mapping in resolved] == chain


def test_a_company_override_lives_alongside_the_general_chain(session: Session) -> None:
    company = make_company(session)
    session.add(
        MetricDefinition(
            code="revenue",
            display_name_he="הכנסות",
            display_name_en="Revenue",
            category="growth",
            metric_type="reported",
            unit_type="currency",
        )
    )
    session.flush()

    session.add_all(
        [
            ConceptMapping(
                provider="magna_xbrl",
                raw_concept="ifrs-full:Revenue",
                metric_code="revenue",
                priority=0,
            ),
            ConceptMapping(
                provider="magna_xbrl",
                raw_concept="ifrs-full:Revenue",
                metric_code="revenue",
                priority=0,
                company_id=company.id,
            ),
        ]
    )
    session.flush()

    assert session.query(ConceptMapping).count() == 2


def test_a_duplicate_mapping_in_the_same_scope_is_rejected(session: Session) -> None:
    session.add(
        MetricDefinition(
            code="revenue",
            display_name_he="הכנסות",
            display_name_en="Revenue",
            category="growth",
            metric_type="reported",
            unit_type="currency",
        )
    )
    session.flush()

    for _ in range(2):
        session.add(
            ConceptMapping(
                provider="magna_xbrl",
                raw_concept="ifrs-full:Revenue",
                metric_code="revenue",
                priority=0,
            )
        )

    with pytest.raises(IntegrityError, match="uq_mapping_concept_scope_version"):
        session.flush()


# -- company identity -----------------------------------------------------


def test_a_company_is_unique_per_provider_entity(session: Session) -> None:
    make_company(session, "520039413")

    with pytest.raises(IntegrityError, match="uq_company_provider_entity"):
        make_company(session, "520039413")


def test_recency_is_recorded_as_inferred(session: Session) -> None:
    """Decision 0009: MAGNA gives no publication date, and we say so."""
    company = make_company(session)
    filing = make_filing(session, company, "2024-01-616266")

    assert filing.published_at is None
    assert filing.recency_source is RecencySource.INFERRED
    assert filing.recency_key == "2024-01-616266"


def test_an_unknown_currency_code_is_too_long_to_store(session: Session) -> None:
    """Currency is ISO 4217, three characters. Nothing longer gets in."""
    company = make_company(session)
    filing = make_filing(session, company, "2023-01-104698")
    period = make_period(session, company, "2023-Q3")

    fact = make_fact(session, company, filing, period)
    fact.currency = "SHEKEL"

    with pytest.raises(DataError):
        session.flush()
