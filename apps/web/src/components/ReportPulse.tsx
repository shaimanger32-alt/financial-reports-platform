import type { PulseBand } from "@/lib/api";
import type { Dictionary } from "@/lib/i18n";

import styles from "./ReportPulse.module.css";

/**
 * The five dimensions, at a glance (spec section 6.1).
 *
 * A state and never a score. Section 6.1 is explicit — "לא להציג בהכרח ציון
 * 0-100" — because a number invites a league table, and this product does not
 * grade companies.
 *
 * Every band is a summary of the findings below it and adds no judgement of its
 * own: its state is read off signals that already fired against thresholds
 * settled long before. A reader who distrusts a band can scroll down and check
 * exactly what it was built from.
 *
 * `not reported` is a first-class state rather than a blank. A bank has no
 * collection days and no inventory, so its working capital band says so — which
 * is information, where an empty row would read as an omission.
 */
export function ReportPulse({ bands, dictionary }: { bands: PulseBand[]; dictionary: Dictionary }) {
  if (bands.length === 0) return null;

  const hasUnreported = bands.some((band) => band.state === "no_data");

  return (
    <section className={styles.block}>
      <h2 className={styles.blockTitle}>{dictionary.pulse.title}</h2>

      <dl className={styles.bands}>
        {bands.map((band) => (
          <div key={band.code} className={styles.band} data-state={band.state}>
            <dt className={styles.name}>
              <span className={styles.mark} aria-hidden />
              {dictionary.pulse.dimensions[band.code] ?? band.code}
            </dt>
            <dd className={styles.state}>{dictionary.pulse.states[band.state] ?? band.state}</dd>
          </div>
        ))}
      </dl>

      {hasUnreported && <p className={styles.note}>{dictionary.pulse.noDataNote}</p>}
    </section>
  );
}
