/**
 * Turning figures into text, in the reader's language.
 *
 * Currency is never hard-coded to the shekel (spec section 45), and a margin
 * movement is always percentage points rather than percent (section 13.2) —
 * calling a move from 9.1% to 10.0% "+9.9%" is the classic way to overstate a
 * small change.
 *
 * Every function takes a locale rather than reading a module-level constant.
 * That constant was `he-IL`, and it was silently rendering American companies'
 * figures with Hebrew conventions.
 */

import type { UnitType } from "./api";
import type { Dictionary, Locale } from "./i18n";
import { getDictionary, intlLocaleOf } from "./i18n";

const CURRENCY_SYMBOLS: Record<string, string> = {
  ILS: "₪",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

export function formatCurrency(value: number, locale: Locale, currency = "USD"): string {
  const millions = value / 1_000_000;
  const formatted = new Intl.NumberFormat(intlLocaleOf(locale), {
    maximumFractionDigits: Math.abs(millions) >= 100 ? 0 : 1,
  }).format(millions);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  // The symbol leads in English and trails in Hebrew, which is how each
  // language actually writes money.
  return locale === "he" ? `${formatted}M ${symbol}` : `${symbol}${formatted}M`;
}

export function formatRatio(value: number, locale: Locale): string {
  return new Intl.NumberFormat(intlLocaleOf(locale), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number, locale: Locale, digits = 1): string {
  return new Intl.NumberFormat(intlLocaleOf(locale), {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatDays(value: number, locale: Locale): string {
  const formatted = new Intl.NumberFormat(intlLocaleOf(locale), {
    maximumFractionDigits: 1,
  }).format(value);
  return getDictionary(locale).units.days(formatted);
}

export function formatSigned(value: number, locale: Locale, digits = 1): string {
  // Intl renders a value that rounds to nothing as "-0", which reads as a real
  // negative. Collapse it first.
  const rounded = Number(value.toFixed(digits));
  const safe = Object.is(rounded, -0) ? 0 : rounded;
  const sign = safe > 0 ? "+" : "";
  return (
    sign +
    new Intl.NumberFormat(intlLocaleOf(locale), { maximumFractionDigits: digits }).format(safe)
  );
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
  "short_term_debt_share",
]);

/** Metrics already expressed in percentage points by their formula. */
const POINT_METRICS = new Set([
  "gross_margin_change_pp",
  "operating_margin_change_pp",
  "net_margin_change_pp",
  "receivables_growth_gap",
  "inventory_growth_gap",
]);

function points(value: number, locale: Locale, dictionary: Dictionary, digits = 2): string {
  return dictionary.units.points(formatSigned(value, locale, digits));
}

export function formatMetric(
  code: string,
  value: number | null,
  unitType: UnitType,
  locale: Locale,
  currency = "USD",
): string {
  if (value === null) return "—";
  const dictionary = getDictionary(locale);
  if (POINT_METRICS.has(code)) return points(value, locale, dictionary);
  if (PERCENT_METRICS.has(code)) return formatPercent(value, locale);

  switch (unitType) {
    case "currency":
      return formatCurrency(value, locale, currency);
    case "days":
      return formatDays(value, locale);
    case "count":
      return new Intl.NumberFormat(intlLocaleOf(locale), { maximumFractionDigits: 1 }).format(
        value,
      );
    default:
      return formatRatio(value, locale);
  }
}

/**
 * A year-on-year movement, in the units the metric is read in.
 *
 * A margin that moved from 8.7% to 9.8% moved by 1.1 percentage points. Showing
 * the raw 0.011 is technically the number and tells the reader nothing, and
 * showing it as a percentage would claim a 12% move (spec section 13.2).
 */
export function formatChange(
  code: string,
  value: number | null,
  unitType: UnitType,
  locale: Locale,
): string {
  if (value === null) return "—";
  const dictionary = getDictionary(locale);
  if (POINT_METRICS.has(code)) return points(value, locale, dictionary);
  if (PERCENT_METRICS.has(code)) return points(value * 100, locale, dictionary);

  switch (unitType) {
    case "days":
      return dictionary.units.days(formatSigned(value, locale, 1));
    case "currency":
      return `${formatSigned(value / 1_000_000, locale, 1)}M`;
    default:
      return formatSigned(value, locale, 2);
  }
}

/**
 * A period code as a reader sees it.
 *
 * Fiscal, not calendar. Apple's first quarter ends in December, and calling it
 * anything else would contradict the company's own report.
 */
export function formatPeriod(code: string, locale: Locale): string {
  const dictionary = getDictionary(locale);

  const quarter = code.match(/^(\d{4})-Q([1-4])$/);
  if (quarter) return dictionary.ui.quarter(Number(quarter[2]), Number(quarter[1]));

  const annual = code.match(/^(\d{4})-FY$/);
  if (annual) return dictionary.ui.fiscalYear(Number(annual[1]));

  const ytd = code.match(/^(\d{4})-YTD-Q([1-4])$/);
  if (ytd) return dictionary.ui.yearToDate(Number(ytd[2]), Number(ytd[1]));

  return code;
}
