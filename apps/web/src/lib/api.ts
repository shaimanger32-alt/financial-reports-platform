/**
 * Server-side access to the FastAPI service.
 *
 * The web app computes nothing. Every figure on screen came from a stored
 * snapshot and arrived over this module (spec section 51, decision 2), which is
 * what keeps one financial truth in one place.
 */

export type Severity = "info" | "positive" | "watch" | "warning" | "critical";
export type Confidence = "low" | "medium" | "high";
export type UnitType = "currency" | "ratio" | "days" | "count";
export type Tier = "core" | "extended";

export interface HealthResponse {
  status: "ok" | "degraded";
  database: "ok" | "error";
  version: string;
  environment: string;
  detail?: string | null;
}

export interface CompanySummary {
  id: string;
  display_name: string;
  legal_name: string;
  name_en: string | null;
  sector: string | null;
  country: string;
  reporting_currency: string;
}

export interface CompanyDetail extends CompanySummary {
  periods: string[];
  latest_period: string | null;
}

export interface MetricValue {
  code: string;
  name_he: string;
  name_en: string;
  category: string;
  unit_type: UnitType;
  tier: Tier;
  value: number | null;
  formula_version: string;
  warnings: string[];
  missing_inputs: string[];
  inputs: Record<string, number | null>;
}

export interface LineItem {
  code: string;
  name_he: string;
  name_en: string;
  category: string;
  tier: Tier;
  value: number | null;
  raw_concept: string | null;
  origin: "reported" | "derived";
}

export interface SignalValue {
  code: string;
  metric_code: string;
  severity: Severity;
  direction: "up" | "down" | "flat";
  confidence: Confidence;
  message_key: string;
  rule_version: string;
  value: number | null;
  year_on_year_change: number | null;
  usual_change: number | null;
  deviation: number | null;
  periods_persisted: number;
}

export type ExplanationStatus = "not_searched" | "no_evidence" | "supported" | "contradicted";

/**
 * Several signals a rule recognises as one thing (spec section 16).
 *
 * It holds the codes of its members rather than copies of them: a pattern has
 * no content of its own beyond the combination, and the codes are what let the
 * page fold those signals underneath it instead of listing them twice.
 */
export interface PatternValue {
  code: string;
  severity: Severity;
  confidence: Confidence;
  message_key: string;
  rule_version: string;
  signal_codes: string[];
  optional_signal_codes: string[];
  explanation_status: ExplanationStatus;
}

/** One Report Pulse dimension (spec section 6.1). A state, never a score. */
export interface PulseBand {
  code: string;
  state: "strong" | "stable" | "watch" | "weak" | "no_data";
  message_key: string;
  signal_codes: string[];
}

export interface ReportAnalysis {
  company_id: string;
  period_code: string;
  fiscal_year: number;
  fiscal_quarter: number;
  period_start: string | null;
  period_end: string;
  versions: Record<string, string>;
  line_items: LineItem[];
  metrics: MetricValue[];
  signals: SignalValue[];
  patterns: PatternValue[];
  pulse: PulseBand[];
  generated_at: string;
}

export interface SeriesPoint {
  period: string;
  value: number | null;
}

export interface MetricSeriesResponse {
  company_id: string;
  metric: string;
  name_he: string;
  name_en: string;
  unit_type: UnitType;
  points: SeriesPoint[];
}

export function getApiBaseUrl(): string {
  return process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
}

export class ApiUnavailableError extends Error {}

async function get<T>(path: string): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`;
  let response: Response;

  try {
    response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(8000) });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new ApiUnavailableError(`${url} — ${reason}`);
  }

  if (response.status === 404) {
    throw new NotFoundError(url);
  }
  if (!response.ok) {
    throw new ApiUnavailableError(`${url} — HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export class NotFoundError extends Error {}

export const fetchHealth = () => get<HealthResponse>("/health");
export const fetchCompanies = () => get<CompanySummary[]>("/v1/companies");
export const fetchCompany = (id: string) => get<CompanyDetail>(`/v1/companies/${id}`);

export const fetchLatestReport = (id: string) =>
  get<ReportAnalysis>(`/v1/companies/${id}/reports/latest`);

export const fetchReport = (id: string, period: string) =>
  get<ReportAnalysis>(`/v1/companies/${id}/reports/${period}`);

/**
 * One metric's history, in one period kind.
 *
 * Quarters and years are never requested together: a twelve-month figure beside
 * a three-month one on the same axis is the mixing spec section 14.6 forbids.
 */
export const fetchSeries = (
  id: string,
  metric: string,
  periods: "quarterly" | "annual" = "quarterly",
) => get<MetricSeriesResponse>(`/v1/companies/${id}/series/${metric}?periods=${periods}`);
