"""Company and report endpoints.

Every response here is read from a stored snapshot rather than computed on the
way out (spec section 23). That is what keeps a page view cheap, and it is also
what makes two readers a month apart see the same numbers.

The public identifier is the registrar number rather than an internal id. It is
stable, it is what an Israeli filing is indexed by, and it makes a URL readable.
"""

from typing import Any

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
        metrics=payload["metrics"],
        signals=payload["signals"],
        generated_at=snapshot.generated_at.isoformat(),
    )


@router.get("", response_model=list[CompanySummary])
def list_all() -> list[CompanySummary]:
    """Every company that has been ingested."""
    with session_scope() as session:
        return [_to_summary(company) for company in list_companies(session)]


@router.get("/{company_id}", response_model=CompanyDetail)
def get_company(company_id: str) -> CompanyDetail:
    """One company, with the periods that can be asked for."""
    with session_scope() as session:
        company = find_company(session, company_id)
        if company is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no company {company_id}")

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
        company = find_company(session, company_id)
        if company is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no company {company_id}")

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
        company = find_company(session, company_id)
        if company is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no company {company_id}")

        found = snapshot_for_period(session, company.id, period_code)
        if found is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"{company_id} has no analysis for {period_code}"
            )
        return _to_analysis(*found)


@router.get("/{company_id}/series/{metric_code}", response_model=MetricSeriesResponse)
def get_series(company_id: str, metric_code: str) -> MetricSeriesResponse:
    """One metric across every period, read from stored snapshots.

    Periods where the metric could not be computed appear with a null value
    rather than being skipped, so a gap in a chart is visible as a gap.
    """
    spec = CALCULATED_BY_CODE.get(metric_code)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no metric {metric_code}")

    with session_scope() as session:
        company = find_company(session, company_id)
        if company is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no company {company_id}")

        history = metric_history(session, company.id, metric_code)

    return MetricSeriesResponse(
        company_id=company_id,
        metric=metric_code,
        name_he=spec.name_he,
        name_en=spec.name_en,
        unit_type=spec.unit_type.value,
        points=[SeriesPoint(period=period, value=value) for period, value in history],
    )
