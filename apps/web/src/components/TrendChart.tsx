import type { SeriesPoint } from "@/lib/api";
import type { Locale } from "@/lib/i18n";
import { formatPercent, formatPeriod } from "@/lib/format";

import styles from "./TrendChart.module.css";

/**
 * A company's history for one metric, drawn as bars.
 *
 * Bars rather than a line, deliberately. A line implies continuity between
 * quarters that a set of discrete reporting periods does not have, and — more
 * usefully — a period the issuer never reported can simply be absent, where a
 * line would either bridge the gap or break in a way that reads as a rendering
 * fault.
 *
 * No charting library. Bars and a baseline do not justify a dependency, and
 * spec section 9 asks for nothing added before it is needed.
 *
 * What it says out loud, because a chart nobody can read is decoration:
 * the highest and lowest values, the zero line, the period at each end, and the
 * period being read. Everything else is available on hover.
 */
export function TrendChart({
  points,
  title,
  locale,
  emptyLabel,
  unavailableLabel,
  current,
}: {
  points: SeriesPoint[];
  title: string;
  locale: Locale;
  emptyLabel: string;
  /** What a period with no report says. Never blank: a gap the reader cannot
      name reads as a bug rather than as missing data. */
  unavailableLabel: string;
  /** The period being read, so the chart says where the reader is standing. */
  current?: string;
}) {
  const recent = points.slice(-16);
  const values = recent
    .map((point) => point.value)
    .filter((value): value is number => value !== null);

  if (values.length < 2) {
    return (
      <figure className={styles.figure}>
        <figcaption className={styles.caption}>{title}</figcaption>
        <p className={styles.tooLittle}>{emptyLabel}</p>
      </figure>
    );
  }

  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  // Where zero sits, as a percentage down from the top.
  const zeroLine = (max / span) * 100;

  const highest = Math.max(...values);
  const lowest = Math.min(...values);

  const first = recent.find((point) => point.value !== null);
  const last = [...recent].reverse().find((point) => point.value !== null);

  const summary = `${title}. ${recent
    .filter((point) => point.value !== null)
    .map((point) => `${point.period} ${formatPercent(point.value as number, locale)}`)
    .join("; ")}`;

  return (
    <figure className={styles.figure}>
      <figcaption className={styles.caption}>{title}</figcaption>

      <div className={styles.frame}>
        <div className={styles.scale} aria-hidden>
          <span className={styles.scaleTop}>{formatPercent(highest, locale)}</span>
          {lowest < 0 && (
            <span className={styles.scaleBottom}>{formatPercent(lowest, locale)}</span>
          )}
        </div>

        <div className={styles.plot} role="img" aria-label={summary}>
          <div className={styles.zero} style={{ top: `${zeroLine}%` }} />

          {recent.map((point) => {
            const isCurrent = point.period === current;

            if (point.value === null) {
              return (
                <div
                  key={point.period}
                  className={styles.gap}
                  title={`${formatPeriod(point.period, locale)} — ${unavailableLabel}`}
                />
              );
            }

            const height = (Math.abs(point.value) / span) * 100;
            const offset = point.value >= 0 ? zeroLine - height : zeroLine;

            return (
              <div
                key={point.period}
                className={styles.column}
                data-current={isCurrent}
                title={`${formatPeriod(point.period, locale)} — ${formatPercent(point.value, locale)}`}
              >
                <div
                  className={point.value >= 0 ? styles.bar : styles.barNegative}
                  style={{ height: `${Math.max(height, 0.8)}%`, top: `${offset}%` }}
                />
                {isCurrent && <span className={styles.marker} aria-hidden />}
              </div>
            );
          })}
        </div>
      </div>

      <div className={styles.axis} aria-hidden>
        <span>{first && formatPeriod(first.period, locale)}</span>
        {last && (
          <span className={styles.latest}>
            {formatPeriod(last.period, locale)}
            <span className="tnum"> {formatPercent(last.value as number, locale)}</span>
          </span>
        )}
      </div>
    </figure>
  );
}
