import Link from "next/link";
import { notFound } from "next/navigation";

import { CategorySection } from "@/components/CategorySection";
import { MetricRow } from "@/components/MetricRow";
import { ReportPulse } from "@/components/ReportPulse";
import { TrendChart } from "@/components/TrendChart";
import {
  ApiUnavailableError,
  NotFoundError,
  fetchCompany,
  fetchLatestReport,
  fetchReport,
  fetchSeries,
  type MetricValue,
  type PatternValue,
  type ReportAnalysis,
  type SignalValue,
} from "@/lib/api";
import { PeriodSwitch } from "@/components/PeriodSwitch";
import { formatChange, formatMetric, formatPeriod } from "@/lib/format";
import {
  type Dictionary,
  type Locale,
  explainMissing,
  explanationStatusLabel,
  getDictionary,
  patternMessage,
  signalMessage,
} from "@/lib/i18n";

import styles from "./CompanyReport.module.css";

/** The figures a reader gets before anything is asked of them. */
const HEADLINE_LINE_ITEMS = ["revenue", "operating_profit", "net_income", "operating_cash_flow"];
const HEADLINE_METRICS = ["revenue_growth_yoy", "operating_margin"];

/** Profit first, then whether it became cash. That order is the product's view. */
const CATEGORY_ORDER = [
  "income",
  "cash_flow",
  "working_capital",
  "balance_sheet",
  "solvency",
  "shareholder",
];

/**
 * One company, one period.
 *
 * Shared by the company URL, which shows the most recent quarter, and by the
 * per-period URL. Both render the same thing; only which snapshot is fetched
 * differs, and a period a reader can link to is worth its own address.
 */
export async function CompanyReport({
  id,
  locale,
  period,
}: {
  id: string;
  locale: Locale;
  period?: string;
}) {
  const t = getDictionary(locale);

  let company;
  let report: ReportAnalysis;
  try {
    [company, report] = await Promise.all([
      fetchCompany(id),
      period ? fetchReport(id, period) : fetchLatestReport(id),
    ]);
  } catch (error) {
    if (error instanceof NotFoundError) notFound();
    return (
      <main className={styles.page}>
        <p className={styles.offline}>
          {t.ui.serverUnreachable}
          <span className={styles.offlineDetail}>
            {error instanceof ApiUnavailableError ? error.message : String(error)}
          </span>
        </p>
      </main>
    );
  }

  // The chart follows the period being read. Looking at a full year and being
  // shown a quarterly trend invites reading one as the other.
  const isAnnual = report.period_code.endsWith("-FY");
  const revenueSeries = await fetchSeries(
    id,
    "revenue_growth_yoy",
    isAnnual ? "annual" : "quarterly",
  ).catch(() => null);

  const lineItems = new Map(report.line_items.map((item) => [item.code, item]));
  const metrics = new Map(report.metrics.map((metric) => [metric.code, metric]));
  const currency = company.reporting_currency;
  // A metric's display name comes from the API, which carries both languages.
  const nameOf = (item: { name_he: string; name_en: string }) =>
    locale === "he" ? item.name_he : item.name_en;

  const byCategory = new Map<string, MetricValue[]>();
  for (const metric of report.metrics) {
    byCategory.set(metric.category, [...(byCategory.get(metric.category) ?? []), metric]);
  }
  const categories = CATEGORY_ORDER.filter((category) => byCategory.has(category));

  // Back points the way the reader came from: leftward in English,
  // rightward in Hebrew.
  const back = locale === "he" ? "→" : "←";

  return (
    <main className={styles.page}>
      <nav className={styles.back}>
        <Link href={`/${locale}`}>{`${back} ${t.ui.allCompanies}`}</Link>
      </nav>

      <header className={styles.masthead}>
        {/* The legal name is the company's own. It is never translated. */}
        <h1 className={`${styles.name} name`}>
          {locale === "he" ? company.legal_name : (company.name_en ?? company.legal_name)}
        </h1>
        <p className={styles.meta}>
          {company.sector}
          {company.sector && <span className={styles.dot}>·</span>}
          {formatPeriod(report.period_code, locale)}
          <span className={styles.dot}>·</span>
          <span className="ltr tnum">{report.period_end}</span>
        </p>
      </header>

      <PeriodSwitch
        locale={locale}
        companyId={id}
        periods={company.periods}
        current={report.period_code}
        dictionary={t}
      />

      <ReportPulse bands={report.pulse} dictionary={t} />

      <Findings
        patterns={report.patterns}
        signals={report.signals}
        metrics={metrics}
        dictionary={t}
        locale={locale}
      />

      <section className={styles.block}>
        <h2 className={styles.blockTitle}>
          {isAnnual ? t.ui.yearInNumbers : t.ui.quarterInNumbers}
        </h2>
        <div className={styles.headline}>
          {HEADLINE_LINE_ITEMS.map((code) => {
            const item = lineItems.get(code);
            if (!item) return null;
            return (
              <HeadlineFigure
                key={code}
                label={nameOf(item)}
                value={formatMetric(code, item.value, "currency", locale, currency)}
                available={item.value !== null}
              />
            );
          })}
          {HEADLINE_METRICS.map((code) => {
            const metric = metrics.get(code);
            if (!metric) return null;
            return (
              <HeadlineFigure
                key={code}
                label={nameOf(metric)}
                value={formatMetric(code, metric.value, metric.unit_type, locale, currency)}
                available={metric.value !== null}
              />
            );
          })}
        </div>
      </section>

      {revenueSeries && (
        <section className={styles.block}>
          <h2 className={styles.blockTitle}>{t.ui.trend}</h2>
          <TrendChart
            points={revenueSeries.points}
            title={t.ui.revenueTrendTitle}
            locale={locale}
            emptyLabel={t.ui.notEnoughHistory}
            unavailableLabel={t.ui.periodUnavailable}
            current={report.period_code}
          />
        </section>
      )}

      <section className={styles.block}>
        <h2 className={styles.blockTitle}>{t.ui.deepDive}</h2>
        <p className={styles.hint}>{t.ui.deepDiveHint}</p>

        {categories.map((category, index) => {
          const items = byCategory.get(category) ?? [];
          const available = items.filter((metric) => metric.value !== null).length;
          return (
            <CategorySection
              key={category}
              category={category}
              available={available}
              total={items.length}
              dictionary={t}
              defaultOpen={index === 0}
            >
              {items.map((metric) => (
                <MetricRow
                  key={metric.code}
                  code={metric.code}
                  label={nameOf(metric)}
                  value={formatMetric(
                    metric.code,
                    metric.value,
                    metric.unit_type,
                    locale,
                    currency,
                  )}
                  available={metric.value !== null}
                  dictionary={t}
                  note={
                    metric.value === null
                      ? explainMissing(t, metric.warnings, metric.missing_inputs)
                      : undefined
                  }
                  isCore={metric.tier === "core"}
                />
              ))}
            </CategorySection>
          );
        })}
      </section>

      <section className={styles.block}>
        <h2 className={styles.blockTitle}>{t.ui.reportedLines}</h2>
        <p className={styles.hint}>{t.ui.reportedLinesHint}</p>
        <div className={styles.reported}>
          {report.line_items
            .filter((item) => item.value !== null)
            .map((item) => (
              <MetricRow
                key={item.code}
                code={item.code}
                label={nameOf(item)}
                value={formatMetric(item.code, item.value, "currency", locale, currency)}
                available
                dictionary={t}
                source={item.raw_concept}
                isCore={item.tier === "core"}
              />
            ))}
        </div>
      </section>

      <footer className={styles.colophon}>
        <p>
          {company.country === "IL" ? "MAGNA, Israel Securities Authority" : "SEC EDGAR"}
          <span className={styles.dot}>·</span>
          {t.ui.sourceNote}
        </p>
        <p className={styles.versions}>
          {t.ui.versions.formulas} <span className="ltr">{report.versions.metrics}</span>
          <span className={styles.dot}>·</span>
          {t.ui.versions.rules} <span className="ltr">{report.versions.rules}</span>
          <span className={styles.dot}>·</span>
          {t.ui.versions.thresholds} <span className="ltr">{report.versions.thresholds}</span>
          <span className={styles.dot}>·</span>
          {t.ui.versions.mappings} <span className="ltr">{report.versions.mappings}</span>
          {report.versions.patterns && (
            <>
              <span className={styles.dot}>·</span>
              {t.ui.versions.patterns} <span className="ltr">{report.versions.patterns}</span>
            </>
          )}
          {report.versions.tiering && (
            <>
              <span className={styles.dot}>·</span>
              {t.ui.versions.tiering} <span className="ltr">{report.versions.tiering}</span>
            </>
          )}
        </p>
      </footer>
    </main>
  );
}

function HeadlineFigure({
  label,
  value,
  available,
}: {
  label: string;
  value: string;
  available: boolean;
}) {
  return (
    <div className={styles.figure}>
      <div className={styles.figureLabel}>{label}</div>
      <div className={available ? `${styles.figureValue} tnum` : styles.figureAbsent}>{value}</div>
    </div>
  );
}

/**
 * What the quarter showed: patterns first, then observations that stand alone.
 *
 * A signal a pattern is made of is shown underneath that pattern rather than
 * again on its own. Hilan's fourth quarter is why: cash conversion falling and
 * the accruals proxy rising are one event seen twice, and listing them as two
 * findings tells a reader that two things went wrong.
 */
function Findings({
  patterns,
  signals,
  metrics,
  dictionary,
  locale,
}: {
  patterns: PatternValue[];
  signals: SignalValue[];
  metrics: Map<string, MetricValue>;
  dictionary: Dictionary;
  locale: Locale;
}) {
  const byCode = new Map(signals.map((signal) => [signal.code, signal]));
  const absorbed = new Set(
    patterns.flatMap((pattern) => [...pattern.signal_codes, ...pattern.optional_signal_codes]),
  );
  const loose = signals.filter((signal) => !absorbed.has(signal.code));

  if (patterns.length === 0 && signals.length === 0) {
    return (
      <section className={styles.block}>
        <h2 className={styles.blockTitle}>{dictionary.ui.whatStandsOut}</h2>
        <p className={styles.quiet}>{dictionary.ui.nothingStoodOut}</p>
      </section>
    );
  }

  return (
    <section className={styles.block}>
      <h2 className={styles.blockTitle}>{dictionary.ui.whatStandsOut}</h2>

      {patterns.map((pattern) => {
        const { title, body } = patternMessage(dictionary, pattern.message_key);
        const members = [...pattern.signal_codes, ...pattern.optional_signal_codes]
          .map((code) => byCode.get(code))
          .filter((signal): signal is SignalValue => signal !== undefined);

        return (
          <article key={pattern.code} className={styles.pattern} data-severity={pattern.severity}>
            <span className={styles.severityMark} aria-hidden />
            <div className={styles.patternBody}>
              <h3 className={styles.patternTitle}>{title}</h3>
              <p className={styles.patternText}>{body}</p>
              <p className={styles.signalDetail}>
                <span className={styles.severityLabel}>
                  {dictionary.severity[pattern.severity]}
                </span>
                <span className={styles.dot}>·</span>
                {dictionary.patternConfidence[pattern.confidence]}
                <span className={styles.dot}>·</span>
                {explanationStatusLabel(dictionary, pattern.explanation_status)}
              </p>

              <p className={styles.patternBasis}>{dictionary.ui.patternBasis}</p>
              <ul className={styles.signals}>
                {members.map((signal) => (
                  <SignalItem
                    key={signal.code}
                    signal={signal}
                    metrics={metrics}
                    dictionary={dictionary}
                    locale={locale}
                  />
                ))}
              </ul>
            </div>
          </article>
        );
      })}

      {loose.length > 0 && (
        <ul className={styles.signals}>
          {loose.map((signal) => (
            <SignalItem
              key={signal.code}
              signal={signal}
              metrics={metrics}
              dictionary={dictionary}
              locale={locale}
            />
          ))}
        </ul>
      )}

      <p className={styles.disclaimer}>
        {patterns.length > 0 ? dictionary.ui.observationsOnly : dictionary.ui.signalsFooter}
      </p>
    </section>
  );
}

function SignalItem({
  signal,
  metrics,
  dictionary,
  locale,
}: {
  signal: SignalValue;
  metrics: Map<string, MetricValue>;
  dictionary: Dictionary;
  locale: Locale;
}) {
  const unit = metrics.get(signal.metric_code)?.unit_type ?? "ratio";
  return (
    <li className={styles.signal} data-severity={signal.severity}>
      <span className={styles.severityMark} aria-hidden />
      <div className={styles.signalBody}>
        <p className={styles.signalText}>{signalMessage(dictionary, signal.message_key)}</p>
        <p className={styles.signalDetail}>
          <span className={styles.severityLabel}>{dictionary.severity[signal.severity]}</span>
          <span className={styles.dot}>·</span>
          {dictionary.ui.yearOnYearChange}{" "}
          <span className="tnum">
            {formatChange(signal.metric_code, signal.year_on_year_change, unit, locale)}
          </span>
          {signal.usual_change !== null && (
            <>
              <span className={styles.dot}>·</span>
              {dictionary.ui.usualChange}{" "}
              <span className="tnum">
                {formatChange(signal.metric_code, signal.usual_change, unit, locale)}
              </span>
            </>
          )}
          <span className={styles.dot}>·</span>
          {signal.periods_persisted > 1
            ? dictionary.ui.persisted(signal.periods_persisted)
            : dictionary.ui.singleQuarter}
        </p>
      </div>
    </li>
  );
}
