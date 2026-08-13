"""Company and report endpoints.

Every response here is read from a stored snapshot rather than computed on the
way out (spec section 23). That is what keeps a page view cheap, and it is also
what makes two readers a month apart see the same numbers.

The public identifier is the registrar number rather than an internal id. It is
stable, it is what an Israeli filing is indexed by, and it makes a URL readable.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status

from api.schemas import (
    CompanyDetail,
    CompanySummary,
    MetricSeriesResponse,
    ReportAnalysis,
    SeriesPoint,
)
from database import session_scope
from database.repository import (
    available_periods,
    find_company,
    latest_snapshot,
    list_companies,
    metric_history,
    snapshot_for_period,
)
from financial_core.metrics import CALCULATED_BY_CODE
from financial_core.periods import DurationKind

router = APIRouter(prefix="/v1/companies", tags=["companies"])


def _to_summary(company: Any) -> CompanySummary:
    return CompanySummary(
        id=company.provider_entity_id,
        display_name=company.display_name,
        legal_name=company.legal_name,
        name_en=company.name_en,
        sector=company.sector_name,
        country=company.country,
        reporting_currency=company.reporting_currency,
    )


def _to_analysis(snapshot: Any, period: Any) -> ReportAnalysis:
    payload = dict(snapshot.payload_json)
    return ReportAnalysis(
        company_id=payload["company_id"],
        period_code=period.code,
        fiscal_year=period.fiscal_year,
        fiscal_quarter=period.fiscal_quarter,
        period_start=period.period_start.isoformat() if period.period_start else None,
        period_end=period.period_end.isoformat(),
        versions=payload["versions"],
        line_items=payload.get("line_items", []),
        metrics=payload["metrics"],
        signals=payload["signals"],
        # Absent on a snapshot generated before the pattern engine existed,
        # which is not the same as a period in which no pattern was found.
        patterns=payload.get("patterns", []),
        # Absent on a snapshot generated before the quality engine was wired in,
        # which is not the same as a period whose identities all held.
        identities=payload.get("identities", []),
        restatements=payload.get("restatements", []),
        pulse=payload.get("pulse", []),
        generated_at=snapshot.generated_at.isoformat(),
    )


def _published_company(session: Any, company_id: str) -> Any:
    """The company, or 404.

    An unpublished company is reported as absent rather than as forbidden. It is
    not a permissions boundary -- it is a company we have loaded and have not
    put in front of a reader -- and saying "exists but you may not see it" would
    disclose more than it withholds.
    """
    company = find_company(session, company_id)
    if company is None or not company.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no company {company_id}")
    return company


@router.get("", response_model=list[CompanySummary])
def list_all() -> list[CompanySummary]:
    """Every company that has been ingested."""
    with session_scope() as session:
        return [_to_summary(company) for company in list_companies(session)]


@router.get("/{company_id}", response_model=CompanyDetail)
def get_company(company_id: str) -> CompanyDetail:
    """One company, with the periods that can be asked for."""
    with session_scope() as session:
        company = _published_company(session, company_id)

        periods = available_periods(session, company.id)
        summary = _to_summary(company)

    return CompanyDetail(
        **summary.model_dump(),
        periods=periods,
        latest_period=periods[-1] if periods else None,
    )


@router.get("/{company_id}/reports/latest", response_model=ReportAnalysis)
def get_latest_report(company_id: str) -> ReportAnalysis:
    """The most recent quarter with an analysis."""
    with session_scope() as session:
        company = _published_company(session, company_id)

        found = latest_snapshot(session, company.id)
        if found is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"{company_id} has no analysis yet; ingest and generate snapshots first",
            )
        return _to_analysis(*found)


@router.get("/{company_id}/reports/{period_code}", response_model=ReportAnalysis)
def get_report(company_id: str, period_code: str) -> ReportAnalysis:
    """One named period, for example 2024-Q3."""
    with session_scope() as session:
        company = _published_company(session, company_id)

        found = snapshot_for_period(session, company.id, period_code)
        if found is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"{company_id} has no analysis for {period_code}"
            )
        return _to_analysis(*found)


@router.get("/{company_id}/series/{metric_code}", response_model=MetricSeriesResponse)
def get_series(
    company_id: str,
    metric_code: str,
    periods: Literal["quarterly", "annual"] = "quarterly",
) -> MetricSeriesResponse:
    """One metric across every period of one kind, read from stored snapshots.

    Periods where the metric could not be computed appear with a null value
    rather than being skipped, so a gap in a chart is visible as a gap.

    Quarters and full years are never returned together. A twelve-month figure
    beside a three-month one on the same axis is the mixing section 14.6
    forbids, and it would read as a company that quadrupled every fourth bar.
    """
    spec = CALCULATED_BY_CODE.get(metric_code)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no metric {metric_code}")

    duration_kind = DurationKind.ANNUAL if periods == "annual" else DurationKind.QUARTER

    with session_scope() as session:
        company = _published_company(session, company_id)

        history = metric_history(session, company.id, metric_code, duration_kind)

    return MetricSeriesResponse(
        company_id=company_id,
        metric=metric_code,
        metric_periods=periods,
        name_he=spec.name_he,
        name_en=spec.name_en,
        unit_type=spec.unit_type.value,
        points=[SeriesPoint(period=period, value=value) for period, value in history],
    )
