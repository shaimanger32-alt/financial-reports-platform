/**
 * The wording. All of it, in one place.
 *
 * The engine ships message keys and never sentences (spec section 42). That
 * boundary is what makes the phrasing rules enforceable: every string a reader
 * can see is written here, so "collection has lengthened" versus "the company
 * is stuffing the channel" is a review of one file rather than an audit of a
 * codebase.
 *
 * Section 42 in practice, for the strings below:
 *   permitted — the collection period lengthened
 *   forbidden — the company is pushing product onto customers
 *   permitted — inventory grew faster than sales
 *   forbidden — a write-down is coming next quarter
 *   permitted — interest cover weakened
 *   forbidden — the company is about to breach a covenant
 *
 * Nothing here states a cause. A cause needs an explicit quote from the filing,
 * which is the evidence engine's job in phase 6.
 */

import type { Confidence, Severity } from "./api";

export const SIGNAL_MESSAGES: Record<string, string> = {
  "signal.liquidity_deterioration": "הנזילות נחלשה ביחס לרגיל בחברה",
  "signal.leverage_increase": "המינוף עלה ביחס לרגיל בחברה",
  "signal.equity_erosion": "חלקו של ההון במאזן ירד",
  "signal.earnings_cash_divergence": "הרווח מתורגם למזומן פחות טוב מבעבר",
  "signal.accruals_elevated": "הפער בין הרווח החשבונאי לתזרים התרחב",
  "signal.operating_cash_deterioration": "התזרים מפעילות שוטפת נחלש",
  "signal.profit_acceleration": "הרווח הנקי צמח מעבר לקצב הרגיל",
  "signal.tax_rate_increase": "שיעור המס האפקטיבי עלה",
  "signal.revenue_acceleration": "ההכנסות צמחו מעבר לקצב הרגיל",
  "signal.margin_expansion": "המרווח התפעולי התרחב",
  "signal.margin_compression": "המרווח הגולמי נשחק",
  "signal.dso_deterioration": "זמן הגבייה מלקוחות התארך",
  "signal.inventory_build": "המלאי גדל מהר יותר מהמכירות",
  "signal.receivables_growth_gap": "יתרת הלקוחות גדלה מהר יותר מההכנסות",
  "signal.debt_build": "החוב נטו עלה",
  "signal.dilution": "מספר המניות המדולל גדל",
};

/** What a null means, in the reader's terms. */
export const WARNING_MESSAGES: Record<string, string> = {
  missing_input: "החברה לא דיווחה את אחד הנתונים",
  non_positive_base: "בסיס ההשוואה אינו חיובי, ולכן אחוז היה מטעה",
  immaterial_denominator: "המכנה קטן מכדי שהיחס יהיה בעל משמעות",
  negative_denominator: "המכנה שלילי, ולכן היחס היה נקרא הפוך",
  derived_input: "אחד הקלטים נגזר על ידינו ולא דווח",
  crossed_zero: "המעבר בין הפסד לרווח מוסתר על ידי אחוז",
  single_period: "נעשה שימוש ביתרה לנקודת זמן ולא בממוצע",
};

export const CONFIDENCE_LABELS: Record<Confidence, string> = {
  low: "רבעון בודד",
  medium: "נמשך שני רבעונים",
  high: "מגובה בהסבר מהדוח",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  info: "לידיעה",
  positive: "חיובי",
  watch: "למעקב",
  warning: "אזהרה",
  critical: "קריטי",
};

export const CATEGORY_LABELS: Record<string, string> = {
  income: "רווח והפסד",
  cash_flow: "תזרים מזומנים",
  working_capital: "הון חוזר",
  balance_sheet: "מאזן",
  solvency: "איתנות פיננסית",
  shareholder: "בעלי מניות",
};

export function signalMessage(key: string): string {
  return SIGNAL_MESSAGES[key] ?? key;
}

export function warningMessage(code: string): string {
  return WARNING_MESSAGES[code] ?? code;
}

/** Why a figure is missing, said plainly rather than left blank. */
export function explainMissing(warnings: string[], missingInputs: string[]): string {
  if (warnings.length > 0) {
    return warningMessage(warnings[0]);
  }
  if (missingInputs.length > 0) {
    return "החברה לא דיווחה: " + missingInputs.join(", ");
  }
  return "לא ניתן לחישוב";
}
