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
    patterns: str | None = Field(
        default=None,
        description="Null on an analysis generated before the pattern engine existed.",
    )
    pulse: str | None = Field(default=None)
    tiering: str | None = Field(
        default=None,
        description=(
            "Which market's tiering decided whether each metric is 'core'. "
            "The current ratio is core in Israel and extended in the United "
            "States, because 11% of American issuers present no current asset "
            "split at all (decision 0011)."
        ),
    )


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


class LineItem(BaseModel):
    """A figure the issuer reported, as opposed to one we computed."""

    code: str
    name_he: str
    name_en: str
    category: str
    tier: Literal["core", "extended"]
    value: float | None
    raw_concept: str | None = Field(
        default=None,
        description="The concept the issuer actually tagged, so a number can be traced.",
    )
    origin: Literal["reported", "derived"]


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


class PatternValue(BaseModel):
    """Several observations that a rule recognises as one thing.

    A pattern is a combination of signals and nothing more (spec section 16).
    It carries the codes of its members rather than copies of them, and a
    `message_key` rather than a sentence: grouping observations never licenses a
    claim about why they happened, which needs a quote from the filing
    (section 42).
    """

    code: str
    severity: Literal["info", "positive", "watch", "warning", "critical"]
    confidence: Literal["low", "medium", "high"] = Field(
        description="'high' requires an explanation from the filing and is never issued here.",
    )
    message_key: str
    rule_version: str
    signal_codes: list[str] = Field(
        description="The signals the pattern is made of. There is nothing else behind it.",
    )
    optional_signal_codes: list[str] = Field(
        default_factory=list,
        description="Signals that corroborate the pattern without deciding it.",
    )
    explanation_status: Literal["not_searched", "no_evidence", "supported", "contradicted"] = Field(
        description="'not_searched' until the evidence engine exists. It is not 'nothing found'.",
    )


class IdentityCheckValue(BaseModel):
    """One accounting identity, run before the analysis (spec section 21.2).

    A broken identity is reported, never hidden. It is also not an accusation:
    far more often it means we mapped a concept to the wrong metric than that
    the issuer added up wrongly, which is exactly why it is worth surfacing.
    """

    name: str
    outcome: Literal["holds", "broken", "not_checkable"] = Field(
        description="'not_checkable' means an input was never reported. Not a failure.",
    )
    expected: float | None = None
    actual: float | None = None
    relative_difference: float | None = Field(
        default=None,
        description="Size of the gap against the larger side, so it can be compared.",
    )
    missing: list[str] = Field(
        default_factory=list,
        description="Inputs the company did not report, which is why the check did not run.",
    )
    unreported_terms: list[str] = Field(
        default_factory=list,
        description=(
            "Reconciling terms the company did not file, recorded rather than "
            "assumed to be zero. A cash bridge that fails at a company filing no "
            "exchange-rate line is more likely our mapping than their accounts."
        ),
    )


class PulseBand(BaseModel):
    """One Report Pulse dimension (spec section 6.1).

    Deliberately a state and not a score: a number invites a league table, and
    this product does not grade companies. The band carries the codes of the
    signals it was read from, so it can always be checked against them.
    """

    code: Literal[
        "growth",
        "profitability",
        "earnings_quality",
        "working_capital",
        "financial_strength",
    ]
    state: Literal["strong", "stable", "watch", "weak", "no_data"] = Field(
        description="'no_data' means the company reports nothing this dimension needs. "
        "It is never a verdict.",
    )
    message_key: str
    signal_codes: list[str] = Field(
        default_factory=list,
        description="The signals the state was read from. Nothing else is behind it.",
    )


class RestatementValue(BaseModel):
    """A figure a later filing of the company's own reported differently.

    Both values are kept (decision 0009). Calculations use the later one, and
    this is how a reader is told that they did — a figure that changes
    underneath someone with nothing said is the failure this prevents.
    """

    metric_code: str
    superseded_value: float
    current_value: float
    superseded_filing: str
    current_filing: str
    relative_difference: float | None = None


class ReportAnalysis(BaseModel):
    """Everything computed for one company and period."""

    company_id: str
    period_code: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: str | None = None
    period_end: str
    versions: AnalysisVersions
    line_items: list[LineItem]
    metrics: list[MetricValue]
    signals: list[SignalValue]
    patterns: list[PatternValue] = Field(default_factory=list)
    identities: list[IdentityCheckValue] = Field(default_factory=list)
    restatements: list[RestatementValue] = Field(default_factory=list)
    pulse: list[PulseBand] = Field(default_factory=list)
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
    metric_periods: Literal["quarterly", "annual"] = Field(
        default="quarterly",
        description="Which period kind the points are. The two are never mixed.",
    )
    name_he: str
    name_en: str
    unit_type: str
    points: list[SeriesPoint]
