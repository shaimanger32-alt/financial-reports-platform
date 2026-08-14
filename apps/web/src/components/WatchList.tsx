import type { Dictionary } from "@/lib/i18n/dictionary";
import { formatChange, formatPeriod } from "@/lib/format";
import type { Locale } from "@/lib/i18n/locale";
import type { MetricValue, WatchItemValue } from "@/lib/api";

import styles from "./WatchList.module.css";

/**
 * What an earlier report asked this one to check (spec section 28).
 *
 * The section shows both readings side by side rather than only the latest.
 * "Collection lengthened 14 days, and now 22" is the item's whole content, and
 * a row carrying one figure could not say what improved.
 *
 * A resolved item is still listed. Dropping it the moment it resolves would
 * mean the only items ever shown are the unresolved ones, which reads as a
 * company that never fixes anything — and would quietly hide the good news the
 * memory exists to report.
 */
export function WatchList({
  items,
  metrics,
  dictionary,
  locale,
}: {
  items: WatchItemValue[];
  metrics: MetricValue[];
  dictionary: Dictionary;
  locale: Locale;
}) {
  if (items.length === 0) return null;

  const nameOf = (code: string) => {
    const metric = metrics.find((entry) => entry.code === code);
    if (!metric) return code;
    return locale === "he" ? metric.name_he : metric.name_en;
  };

  const unitOf = (code: string) =>
    metrics.find((entry) => entry.code === code)?.unit_type ?? "ratio";

  return (
    <section className={styles.block}>
      <h2 className={styles.title}>{dictionary.watch.title}</h2>
      <p className={styles.intro}>{dictionary.watch.intro}</p>

      <ul className={styles.list}>
        {items.map((item) => (
          <li className={styles.item} key={`${item.source_code}-${item.metric_code}`}>
            <div className={styles.head}>
              <span className={styles.metric}>{nameOf(item.metric_code)}</span>
              <span className={styles[statusClass(item.status)]}>
                {dictionary.watch.statuses[item.status_reason] ?? item.status_reason}
              </span>
            </div>

            <dl className={styles.readings}>
              <div className={styles.reading}>
                <dt>
                  {dictionary.watch.then} · {formatPeriod(item.opened_in_period, locale)}
                </dt>
                <dd>
                  {formatChange(
                    item.metric_code,
                    item.opened_from.year_on_year_change,
                    unitOf(item.metric_code),
                    locale,
                  )}
                </dd>
              </div>
              {item.current && (
                <div className={styles.reading}>
                  <dt>
                    {dictionary.watch.now} · {formatPeriod(item.current.period_code, locale)}
                  </dt>
                  <dd>
                    {formatChange(
                      item.metric_code,
                      item.current.year_on_year_change,
                      unitOf(item.metric_code),
                      locale,
                    )}
                  </dd>
                </div>
              )}
            </dl>
          </li>
        ))}
      </ul>
    </section>
  );
}

function statusClass(status: WatchItemValue["status"]) {
  switch (status) {
    case "worsened":
      return "worsened" as const;
    case "improved":
    case "resolved":
      return "improved" as const;
    default:
      return "neutral" as const;
  }
}
