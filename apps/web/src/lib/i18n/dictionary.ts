/**
 * The shape every language has to fill.
 *
 * All user-facing wording lives behind this type. The engine ships message keys
 * and never sentences, which is what keeps spec section 42 reviewable: whether
 * the product ever claims a cause is a question about these files, not about the
 * codebase.
 *
 * A missing key is a type error rather than a silent fallback to English. A page
 * half in one language is worse than a page in the wrong one, because the reader
 * cannot tell which parts they are missing.
 */

import type { Confidence, Severity } from "../api";

export interface Explanation {
  /** What the number is, in one sentence. */
  what: string;
  /** How to read a movement in it, without judging the company. */
  read: string;
  /** What a reader might look at next. Never a prediction. */
  watch?: string;
}

export interface PatternMessage {
  title: string;
  body: string;
}

export interface Dictionary {
  /** Page chrome and navigation. */
  ui: {
    tagline: string;
    strapline: string;
    companies: string;
    allCompanies: string;
    noCompanies: string;
    serverUnreachable: string;
    quarter: (quarter: number, year: number) => string;
    fiscalYear: (year: number) => string;
    yearToDate: (quarter: number, year: number) => string;
    periodUnavailable: string;
    whatStandsOut: string;
    quarterInNumbers: string;
    yearInNumbers: string;
    patternBasis: string;
    observationsOnly: string;
    signalsFooter: string;
    trend: string;
    deepDive: string;
    notComputable: string;
    notReported: (inputs: string) => string;
    singleQuarter: string;
    yearOnYearChange: string;
    usualChange: string;
    sourceConcept: string;
    reported: string;
    derived: string;
    language: string;
    reportedLines: string;
    reportedLinesHint: string;
    deepDiveHint: string;
    nothingStoodOut: string;
    revenueTrendTitle: string;
    sourceNote: string;
    coreMark: string;
    of: string;
    worthWatching: string;
    sourceInFiling: string;
    notEnoughHistory: string;
    searchPlaceholder: string;
    searchLabel: string;
    noMatches: string;
    /** Templates rather than functions: these cross into a client component,
        and a React Server Component may not pass a function over that
        boundary. `{shown}` and `{total}` are replaced where they are shown. */
    searchCountAll: string;
    searchCountFiltered: string;
    periods: string;
    quarters: string;
    years: string;
    persisted: (quarters: number) => string;
    versions: {
      formulas: string;
      rules: string;
      thresholds: string;
      mappings: string;
      patterns: string;
      tiering: string;
    };
  };
  units: {
    days: (formatted: string) => string;
    points: (formatted: string) => string;
  };
  pulse: {
    title: string;
    dimensions: Record<string, string>;
    states: Record<string, string>;
    noDataNote: string;
  };
  signals: Record<string, string>;
  patterns: Record<string, PatternMessage>;
  warnings: Record<string, string>;
  confidence: Record<Confidence, string>;
  patternConfidence: Record<Confidence, string>;
  severity: Record<Severity, string>;
  categories: Record<string, string>;
  categoryIntros: Record<string, string>;
  explanationStatus: Record<string, string>;
  metricExplanations: Record<string, Explanation>;
  lineItemExplanations: Record<string, Explanation>;
}
