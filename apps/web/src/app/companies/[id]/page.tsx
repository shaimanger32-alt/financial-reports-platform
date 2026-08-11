import Link from "next/link";
import { notFound } from "next/navigation";

import { CategorySection } from "@/components/CategorySection";
import { MetricRow } from "@/components/MetricRow";
import { Sparkline } from "@/components/Sparkline";
import {
  ApiUnavailableError,
  NotFoundError,
  fetchCompany,
  fetchLatestReport,
  fetchSeries,
  type MetricValue,
  type ReportAnalysis,
  type SignalValue,
} from "@/lib/api";
import { formatChange, formatMetric, formatPeriod } from "@/lib/format";
import { SEVERITY_LABELS, explainMissing, signalMessage } from "@/lib/messages";

import styles from "./page.module.css";

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

export default async function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let company;
  let report: ReportAnalysis;
  try {
    [company, report] = await Promise.all([fetchCompany(id), fetchLatestReport(id)]);
  } catch (error) {
    if (error instanceof NotFoundError) notFound();
    return (
      <main className={styles.page}>
        <p className={styles.offline}>
          לא ניתן להגיע לשרת.
          <span className={styles.offlineDetail}>
            {error instanceof ApiUnavailableError ? error.message : String(error)}
          </span>
        </p>
      </main>
    );
  }

  const revenueSeries = await fetchSeries(id, "revenue_growth_yoy").catch(() => null);

  const lineItems = new Map(report.line_items.map((item) => [item.code, item]));
  const metrics = new Map(report.metrics.map((metric) => [metric.code, metric]));
  const currency = company.reporting_currency;

  const byCategory = new Map<string, MetricValue[]>();
  for (const metric of report.metrics) {
    byCategory.set(metric.category, [...(byCategory.get(metric.category) ?? []), metric]);
  }
  const categories = CATEGORY_ORDER.filter((category) => byCategory.has(category));

  return (
    <main className={styles.page}>
      <nav className={styles.back}>
        <Link href="/">← כל החברות</Link>
      </nav>

      <header className={styles.masthead}>
        <h1 className={styles.name}>{company.legal_name}</h1>
        <p className={styles.meta}>
          {company.sector}
          <span className={styles.dot}>·</span>
          {formatPeriod(report.period_code)}
          <span className={styles.dot}>·</span>
          <span className="ltr tnum">{report.period_end}</span>
        </p>
      </header>

      <Signals signals={report.signals} metrics={metrics} />

      <section className={styles.block}>
        <h2 className={styles.blockTitle}>הרבעון במספרים</h2>
        <div className={styles.headline}>
          {HEADLINE_LINE_ITEMS.map((code) => {
            const item = lineItems.get(code);
            if (!item) return null;
            return (
              <HeadlineFigure
                key={code}
                label={item.name_he}
                value={formatMetric(code, item.value, "currency", currency)}
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
                label={metric.name_he}
                value={formatMetric(code, metric.value, metric.unit_type, currency)}
                available={metric.value !== null}
              />
            );
          })}
        </div>
      </section>

      {revenueSeries && (
        <section className={styles.block}>
          <h2 className={styles.blockTitle}>מגמה</h2>
          <Sparkline points={revenueSeries.points} title="צמיחת הכנסות, שנה מול שנה" />
        </section>
      )}

      <section className={styles.block}>
        <h2 className={styles.blockTitle}>לעומק</h2>
        <p className={styles.hint}>
          כל קטגוריה נפתחת, וליד כל מדד יש <span className={styles.inlineInfo}>i</span> שמסביר מה
          הוא מודד ואיך קוראים אותו.
        </p>

        {categories.map((category, index) => {
          const items = byCategory.get(category) ?? [];
          const available = items.filter((metric) => metric.value !== null).length;
          return (
            <CategorySection
              key={category}
              category={category}
              available={available}
              total={items.length}
              defaultOpen={index === 0}
            >
              {items.map((metric) => (
                <MetricRow
                  key={metric.code}
                  code={metric.code}
                  label={metric.name_he}
                  value={formatMetric(metric.code, metric.value, metric.unit_type, currency)}
                  available={metric.value !== null}
                  note={
                    metric.value === null
                      ? explainMissing(metric.warnings, metric.missing_inputs)
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
        <h2 className={styles.blockTitle}>שורות הדיווח</h2>
        <p className={styles.hint}>המספרים כפי שהחברה עצמה דיווחה אותם, לפני כל חישוב שלנו.</p>
        <div className={styles.reported}>
          {report.line_items
            .filter((item) => item.value !== null)
            .map((item) => (
              <MetricRow
                key={item.code}
                code={item.code}
                label={item.name_he}
                value={formatMetric(item.code, item.value, "currency", currency)}
                available
                source={item.raw_concept}
                isCore={item.tier === "core"}
              />
            ))}
        </div>
      </section>

      <footer className={styles.colophon}>
        <p>המקור: מגנא, רשות ניירות ערך. כל מספר נגזר מדיווח iXBRL של החברה.</p>
        <p className={styles.versions}>
          נוסחאות <span className="ltr">{report.versions.metrics}</span>
          <span className={styles.dot}>·</span>
          כללים <span className="ltr">{report.versions.rules}</span>
          <span className={styles.dot}>·</span>
          ספים <span className="ltr">{report.versions.thresholds}</span>
          <span className={styles.dot}>·</span>
          מיפוי <span className="ltr">{report.versions.mappings}</span>
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

function Signals({
  signals,
  metrics,
}: {
  signals: SignalValue[];
  metrics: Map<string, MetricValue>;
}) {
  if (signals.length === 0) {
    return (
      <section className={styles.block}>
        <h2 className={styles.blockTitle}>מה בלט בדוח</h2>
        <p className={styles.quiet}>שום מדד לא חרג מהטווח הרגיל של החברה עצמה ברבעון הזה.</p>
      </section>
    );
  }

  return (
    <section className={styles.block}>
      <h2 className={styles.blockTitle}>מה בלט בדוח</h2>
      <ul className={styles.signals}>
        {signals.map((signal) => {
          const unit = metrics.get(signal.metric_code)?.unit_type ?? "ratio";
          return (
            <li key={signal.code} className={styles.signal} data-severity={signal.severity}>
              <span className={styles.severityMark} aria-hidden />
              <div className={styles.signalBody}>
                <p className={styles.signalText}>{signalMessage(signal.message_key)}</p>
                <p className={styles.signalDetail}>
                  <span className={styles.severityLabel}>{SEVERITY_LABELS[signal.severity]}</span>
                  <span className={styles.dot}>·</span>
                  שינוי שנתי{" "}
                  <span className="tnum">
                    {formatChange(signal.metric_code, signal.year_on_year_change, unit)}
                  </span>
                  {signal.usual_change !== null && (
                    <>
                      <span className={styles.dot}>·</span>
                      בדרך כלל{" "}
                      <span className="tnum">
                        {formatChange(signal.metric_code, signal.usual_change, unit)}
                      </span>
                    </>
                  )}
                  <span className={styles.dot}>·</span>
                  {signal.periods_persisted > 1
                    ? `נמשך ${signal.periods_persisted} רבעונים`
                    : "רבעון בודד"}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
      <p className={styles.disclaimer}>
        אלה תצפיות על מספרים. הסיבה להן תיקבע רק כשיימצא הסבר מפורש בדוח עצמו.
      </p>
    </section>
  );
}
