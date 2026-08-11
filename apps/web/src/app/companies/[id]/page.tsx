import Link from "next/link";
import { notFound } from "next/navigation";

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
import { CATEGORY_LABELS, SEVERITY_LABELS, explainMissing, signalMessage } from "@/lib/messages";

import styles from "./page.module.css";

/** The figures a reader wants first, in the order they want them. */
const HEADLINE_LINE_ITEMS = [
  "revenue",
  "gross_profit",
  "operating_profit",
  "net_income",
  "operating_cash_flow",
  "cash_and_equivalents",
];

const HEADLINE_METRICS = [
  "revenue_growth_yoy",
  "gross_margin",
  "operating_margin",
  "net_income_growth_yoy",
  "current_ratio",
  "days_sales_outstanding",
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
        <h2 className={styles.blockTitle}>מספרי מפתח</h2>
        <div className={styles.ledger}>
          {HEADLINE_LINE_ITEMS.map((code) => {
            const item = lineItems.get(code);
            if (!item) return null;
            return (
              <Row
                key={code}
                label={item.name_he}
                value={formatMetric(code, item.value, "currency", currency)}
                available={item.value !== null}
                note={item.value === null ? "לא דווח על ידי החברה" : undefined}
                source={item.raw_concept}
              />
            );
          })}
        </div>

        <div className={styles.ledger}>
          {HEADLINE_METRICS.map((code) => {
            const metric = metrics.get(code);
            if (!metric) return null;
            return <MetricRow key={code} metric={metric} currency={currency} />;
          })}
        </div>
      </section>

      {revenueSeries && (
        <section className={styles.block}>
          <h2 className={styles.blockTitle}>מגמה</h2>
          <Sparkline points={revenueSeries.points} title="צמיחת הכנסות, שנה מול שנה" />
        </section>
      )}

      <AllMetrics report={report} currency={currency} />

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
        {signals.map((signal) => (
          <li key={signal.code} className={styles.signal} data-severity={signal.severity}>
            <span className={styles.severityMark} aria-hidden />
            <div className={styles.signalBody}>
              <p className={styles.signalText}>{signalMessage(signal.message_key)}</p>
              <p className={styles.signalDetail}>
                <span className={styles.severityLabel}>{SEVERITY_LABELS[signal.severity]}</span>
                <span className={styles.dot}>·</span>
                שינוי שנתי{" "}
                <span className="tnum">
                  {formatChange(
                    signal.metric_code,
                    signal.year_on_year_change,
                    metrics.get(signal.metric_code)?.unit_type ?? "ratio",
                  )}
                </span>
                {signal.usual_change !== null && (
                  <>
                    <span className={styles.dot}>·</span>
                    בדרך כלל{" "}
                    <span className="tnum">
                      {formatChange(
                        signal.metric_code,
                        signal.usual_change,
                        metrics.get(signal.metric_code)?.unit_type ?? "ratio",
                      )}
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
        ))}
      </ul>
      <p className={styles.disclaimer}>
        אלה תצפיות על מספרים. הסיבה להן תיקבע רק כשיימצא הסבר מפורש בדוח עצמו.
      </p>
    </section>
  );
}

function MetricRow({ metric, currency }: { metric: MetricValue; currency: string }) {
  return (
    <Row
      label={metric.name_he}
      value={formatMetric(metric.code, metric.value, metric.unit_type, currency)}
      available={metric.value !== null}
      note={
        metric.value === null ? explainMissing(metric.warnings, metric.missing_inputs) : undefined
      }
      tier={metric.tier}
    />
  );
}

function Row({
  label,
  value,
  available,
  note,
  source,
  tier,
}: {
  label: string;
  value: string;
  available: boolean;
  note?: string;
  source?: string | null;
  tier?: string;
}) {
  return (
    <div className={styles.row}>
      <div className={styles.rowLabel}>
        {label}
        {tier === "core" && (
          <span className={styles.coreMark} title="נשען על נתונים שכל חברה מדווחת" />
        )}
      </div>
      <div className={styles.rowValue}>
        <span className={available ? "tnum" : styles.absent}>{value}</span>
        {note && <span className={styles.note}>{note}</span>}
        {source && <span className={styles.source + " ltr"}>{source}</span>}
      </div>
    </div>
  );
}

function AllMetrics({ report, currency }: { report: ReportAnalysis; currency: string }) {
  const byCategory = new Map<string, MetricValue[]>();
  for (const metric of report.metrics) {
    const bucket = byCategory.get(metric.category) ?? [];
    bucket.push(metric);
    byCategory.set(metric.category, bucket);
  }

  return (
    <section className={styles.block}>
      <h2 className={styles.blockTitle}>כל המדדים</h2>
      {[...byCategory.entries()].map(([category, items]) => (
        <div key={category} className={styles.category}>
          <h3 className={styles.categoryTitle}>{CATEGORY_LABELS[category] ?? category}</h3>
          <div className={styles.ledger}>
            {items.map((metric) => (
              <MetricRow key={metric.code} metric={metric} currency={currency} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
