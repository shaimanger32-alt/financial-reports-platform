import type { SeriesPoint } from "@/lib/api";

import styles from "./Sparkline.module.css";

/**
 * A twelve-quarter trend, drawn as bars rather than a line.
 *
 * Bars are the honest shape here. A line implies continuity between quarters
 * that a set of discrete reporting periods does not have, and — more usefully —
 * a period the issuer never reported can simply be absent, where a line would
 * either bridge the gap or break in a way that reads as a data error.
 *
 * No charting library. Twelve rectangles do not justify a dependency, and spec
 * section 9 asks for nothing added before it is needed.
 */
export function Sparkline({ points, title }: { points: SeriesPoint[]; title: string }) {
  const recent = points.slice(-12);
  const values = recent.map((point) => point.value).filter((v): v is number => v !== null);

  if (values.length < 2) {
    return (
      <figure className={styles.figure}>
        <figcaption className={styles.caption}>{title}</figcaption>
        <p className={styles.tooLittle}>אין מספיק היסטוריה לגרף</p>
      </figure>
    );
  }

  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const zeroLine = (max / span) * 100;

  return (
    <figure className={styles.figure}>
      <figcaption className={styles.caption}>{title}</figcaption>
      <div className={styles.plot} role="img" aria-label={title}>
        {min < 0 && <div className={styles.zero} style={{ top: `${zeroLine}%` }} />}
        {recent.map((point) => {
          if (point.value === null) {
            return (
              <div key={point.period} className={styles.gap} title={`${point.period}: לא דווח`} />
            );
          }
          const height = (Math.abs(point.value) / span) * 100;
          const offset = point.value >= 0 ? zeroLine - height : zeroLine;
          return (
            <div key={point.period} className={styles.column}>
              <div
                className={point.value >= 0 ? styles.bar : styles.barNegative}
                style={{ height: `${height}%`, top: `${offset}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className={styles.axis}>
        <span className="ltr tnum">{recent[0]?.period}</span>
        <span className="ltr tnum">{recent[recent.length - 1]?.period}</span>
      </div>
    </figure>
  );
}
