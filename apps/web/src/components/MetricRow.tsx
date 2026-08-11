import { explanationFor } from "@/lib/explanations";

import styles from "./MetricRow.module.css";

/**
 * One figure, with its meaning one click away.
 *
 * The explanation is a `<details>` rather than a tooltip or a popover on
 * purpose. It needs no JavaScript, it survives without hydration, keyboards and
 * screen readers get it for free, and — the part that matters for this product —
 * it can hold three sentences. A tooltip cannot, and three sentences is what it
 * takes to say what an accruals proxy is without lying about it.
 */
export function MetricRow({
  code,
  label,
  value,
  available,
  note,
  source,
  isCore,
}: {
  code: string;
  label: string;
  value: string;
  available: boolean;
  note?: string;
  source?: string | null;
  isCore?: boolean;
}) {
  const explanation = explanationFor(code);

  return (
    <div className={styles.row}>
      <details className={styles.details}>
        <summary className={styles.summary}>
          <span className={styles.label}>
            {label}
            {isCore && <span className={styles.coreMark} title="נתון שכל חברה מדווחת" />}
            {explanation && (
              <span className={styles.info} aria-hidden>
                i
              </span>
            )}
          </span>

          <span className={styles.valueGroup}>
            <span className={available ? `${styles.value} tnum` : styles.absent}>{value}</span>
            {note && <span className={styles.note}>{note}</span>}
          </span>
        </summary>

        {explanation && (
          <div className={styles.body}>
            <p className={styles.what}>{explanation.what}</p>
            <p className={styles.read}>{explanation.read}</p>
            {explanation.watch && (
              <p className={styles.watch}>
                <span className={styles.watchLabel}>שווה מבט</span>
                {explanation.watch}
              </p>
            )}
            {source && (
              <p className={styles.source}>
                מקור בדוח: <span className="ltr">{source}</span>
              </p>
            )}
          </div>
        )}
      </details>
    </div>
  );
}
