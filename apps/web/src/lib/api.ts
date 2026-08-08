/**
 * Server-side access to the FastAPI service.
 *
 * The web app never computes financial values; it only renders what the API
 * returns (spec section 51, decision 2). This module is the single place that
 * knows the API base URL.
 */

export type HealthStatus = "ok" | "degraded";

export interface HealthResponse {
  status: HealthStatus;
  database: "ok" | "error";
  version: string;
  environment: string;
  detail?: string | null;
}

/** Result of a health probe, including the case where the API is unreachable. */
export type HealthProbe =
  { reachable: true; health: HealthResponse } | { reachable: false; error: string };

export function getApiBaseUrl(): string {
  return process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
}

/**
 * Probe the API health endpoint.
 *
 * Never throws: an unreachable API is a state the page must be able to render,
 * not a crash. A 503 from the API still carries a valid body, so it is parsed.
 */
export async function fetchHealth(): Promise<HealthProbe> {
  const url = `${getApiBaseUrl()}/health`;

  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return {
        reachable: false,
        error: `Unexpected response from ${url}: HTTP ${response.status}`,
      };
    }

    return { reachable: true, health: (await response.json()) as HealthResponse };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { reachable: false, error: `${url} — ${reason}` };
  }
}
