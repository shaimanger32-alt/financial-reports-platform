"""Response models. These define the public API contract consumed by web and mobile.

Two things every response carries, because the product's central promise depends
on them (spec sections 4.2 and 4.3):

* **Versions.** A figure that cannot say which formulas and rules produced it
  cannot be audited later.
* **Nulls, kept rather than dropped.** A metric that could not be computed stays
  in the response with `value: null` and the inputs that were missing. Removing
  the row would read as though the metric did not exist, when the truth is that
  the issuer did not report something (section 4.4).
"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness and dependency status of the service."""

    status: Literal["ok", "degraded"] = Field(
        description="'ok' only when every dependency is reachable.",
    )
    database: Literal["ok", "error"] = Field(
        description="Result of a SELECT 1 against the canonical store.",
    )
    version: str = Field(description="Service version.")
    environment: str = Field(description="Deployment environment name.")
    detail: str | None = Field(
        default=None,
        description="Failure reason when status is 'degraded'.",
    )


class CompanySummary(BaseModel):
    """A company as it appears in a list."""

    id: str = Field(description="Registrar number, which is the public identifier.")
    display_name: str
    legal_name: str
    name_en: str | None = None
    sector: str | None = None
    country: str
    reporting_currency: str


class CompanyDetail(CompanySummary):
    """A company with the periods that can be asked for."""

    periods: list[str] = Field(description="Every period with an analysis, oldest first.")
    latest_period: str | None = None


class AnalysisVersions(BaseModel):
    """Which rules produced this answer (spec section 33)."""

    analysis: str
    metrics: str
    rules: str
    thresholds: str
    mappings: str


class MetricValue(BaseModel):
    """One metric, computed or explicitly unavailable."""

    code: str
    name_he: str
    name_en: str
    category: str
    unit_type: Literal["currency", "ratio", "days", "count"]
    tier: Literal["core", "extended"] = Field(
        description="'core' metrics rest only on concepts every issuer tags.",
    )
    value: float | None = Field(description="Null means unknown. It never means zero.")
    formula_version: str
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(
        default_factory=list,
        description="Which inputs were unreported, so a null can be explained.",
    )
    inputs: dict[str, float | None] = Field(default_factory=dict)


class SignalValue(BaseModel):
    """One numeric observation.

    Carries a `message_key`, never a sentence. Wording lives in the client so
    that no engine can assert a cause (spec section 42).
    """

    code: str
    metric_code: str
    severity: Literal["info", "positive", "watch", "warning", "critical"]
    direction: Literal["up", "down", "flat"]
    confidence: Literal["low", "medium", "high"]
    message_key: str
    rule_version: str
    value: float | None = None
    year_on_year_change: float | None = None
    usual_change: float | None = Field(
        default=None,
        description="What this company's year-on-year move usually looks like.",
    )
    deviation: float | None = Field(
        default=None,
        description="Distance from that norm, in robust units.",
    )
    periods_persisted: int = 1


class ReportAnalysis(BaseModel):
    """Everything computed for one company and period."""

    company_id: str
    period_code: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: str | None = None
    period_end: str
    versions: AnalysisVersions
    metrics: list[MetricValue]
    signals: list[SignalValue]
    generated_at: str


class SeriesPoint(BaseModel):
    """One metric in one period."""

    period: str
    value: float | None


class MetricSeriesResponse(BaseModel):
    """A metric's history, read from stored snapshots.

    Charts and report pages read the same source, so they cannot disagree
    (spec section 23).
    """

    company_id: str
    metric: str
    name_he: str
    name_en: str
    unit_type: str
    points: list[SeriesPoint]
