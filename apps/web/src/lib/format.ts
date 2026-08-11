/**
 * Turning figures into text.
 *
 * Currency is never hard-coded to the shekel (spec section 45), and a margin
 * movement is always percentage points rather than percent (section 13.2) —
 * calling a move from 9.1% to 10.0% "+9.9%" is the classic way to overstate a
 * small change.
 */

import type { UnitType } from "./api";

const LOCALE = "he-IL";

export function formatCurrency(value: number, currency = "ILS"): string {
  const millions = value / 1_000_000;
  const formatted = new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits: Math.abs(millions) >= 100 ? 0 : 1,
  }).format(millions);
  const symbol = currency === "ILS" ? "₪" : currency;
  return `${formatted}M ${symbol}`;
}

export function formatRatio(value: number): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatDays(value: number): string {
  return `${new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 }).format(value)} ימים`;
}

export function formatSigned(value: number, digits = 1): string {
  // Intl renders a value that rounds to nothing as "-0", which reads as a real
  // negative. Collapse it first.
  const rounded = Number(value.toFixed(digits));
  const safe = Object.is(rounded, -0) ? 0 : rounded;
  const sign = safe > 0 ? "+" : "";
  return sign + new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits }).format(safe);
}

/** Which metrics are naturally read as a percentage rather than a bare ratio. */
const PERCENT_METRICS = new Set([
  "gross_margin",
  "operating_margin",
  "net_margin",
  "free_cash_flow_margin",
  "effective_tax_rate",
  "equity_ratio",
  "revenue_growth_yoy",
  "gross_profit_growth_yoy",
  "operating_profit_growth_yoy",
  "net_income_growth_yoy",
  "profit_before_tax_growth_yoy",
  "operating_cash_flow_growth_yoy",
  "dilution_yoy",
  "accruals_proxy",
]);

/** Metrics already expressed in percentage points by their formula. */
const POINT_METRICS = new Set([
  "gross_margin_change_pp",
  "operating_margin_change_pp",
  "net_margin_change_pp",
  "receivables_growth_gap",
  "inventory_growth_gap",
]);

export function formatMetric(
  code: string,
  value: number | null,
  unitType: UnitType,
  currency = "ILS",
): string {
  if (value === null) return "—";
  if (POINT_METRICS.has(code)) return `${formatSigned(value, 2)} נק׳`;
  if (PERCENT_METRICS.has(code)) return formatPercent(value);

  switch (unitType) {
    case "currency":
      return formatCurrency(value, currency);
    case "days":
      return formatDays(value);
    case "count":
      return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 }).format(value);
    default:
      return formatRatio(value);
  }
}

/**
 * A year-on-year movement, in the units the metric is read in.
 *
 * A margin that moved from 8.7% to 9.8% moved by 1.1 percentage points. Showing
 * the raw 0.011 is technically the number and tells the reader nothing, and
 * showing it as a percentage would claim a 12% move (spec section 13.2).
 */
export function formatChange(code: string, value: number | null, unitType: UnitType): string {
  if (value === null) return "—";
  if (POINT_METRICS.has(code)) return `${formatSigned(value, 2)} נק׳`;
  if (PERCENT_METRICS.has(code)) return `${formatSigned(value * 100, 2)} נק׳`;

  switch (unitType) {
    case "days":
      return `${formatSigned(value, 1)} ימים`;
    case "currency":
      return `${formatSigned(value / 1_000_000, 1)}M`;
    default:
      return formatSigned(value, 2);
  }
}

export function formatPeriod(code: string): string {
  const quarter = code.match(/^(\d{4})-Q([1-4])$/);
  if (quarter) return `רבעון ${quarter[2]} ${quarter[1]}`;
  const annual = code.match(/^(\d{4})-FY$/);
  if (annual) return `שנת ${annual[1]}`;
  const ytd = code.match(/^(\d{4})-YTD-Q([1-4])$/);
  if (ytd) return `מתחילת ${ytd[1]} עד רבעון ${ytd[2]}`;
  return code;
}
