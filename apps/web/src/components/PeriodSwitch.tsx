import Link from "next/link";

import type { Dictionary, Locale } from "@/lib/i18n";

import styles from "./PeriodSwitch.module.css";

/**
 * Moving between the periods a company has been analysed for.
 *
 * Quarters and years are kept in separate rows rather than one list, because
 * they are different questions and spec section 14.6 forbids reading them as a
 * sequence. A year sitting between two quarters would invite exactly that.
 *
 * Every period is a real URL. A reader who finds something in a particular
 * quarter can link to it, and — the reason this exists at all — the twenty
 * patterns the engine has found are almost all in quarters that are not the
 * latest, so without this they were reachable only through the API.
 */
export function PeriodSwitch({
  locale,
  companyId,
  periods,
  current,
  dictionary,
}: {
  locale: Locale;
  companyId: string;
  periods: string[];
  current: string;
  dictionary: Dictionary;
}) {
  const quarters = periods.filter((code) => /-Q[1-4]$/.test(code));
  const years = periods.filter((code) => code.endsWith("-FY"));

  if (quarters.length + years.length <= 1) return null;

  // Newest first: a reader arrives wanting the recent past, and reads leftward
  // (or rightward in Hebrew) into history.
  const href = (code: string) => `/${locale}/companies/${companyId}/${code}`;

  return (
    <nav className={styles.switch} aria-label={dictionary.ui.periods}>
      {quarters.length > 0 && (
        <div className={styles.group}>
          <span className={styles.label}>{dictionary.ui.quarters}</span>
          <div className={styles.scroller}>
            {[...quarters].reverse().map((code) => (
              <Link
                key={code}
                href={href(code)}
                className={styles.period}
                data-current={code === current}
                aria-current={code === current ? "page" : undefined}
              >
                <span className="ltr tnum">{shortQuarter(code)}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {years.length > 0 && (
        <div className={styles.group}>
          <span className={styles.label}>{dictionary.ui.years}</span>
          <div className={styles.scroller}>
            {[...years].reverse().map((code) => (
              <Link
                key={code}
                href={href(code)}
                className={styles.period}
                data-current={code === current}
                aria-current={code === current ? "page" : undefined}
              >
                <span className="ltr tnum">{code.replace("-FY", "")}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </nav>
  );
}

/** `2026-Q3` reads as `Q3 26` in a row of twenty. */
function shortQuarter(code: string): string {
  const [year, quarter] = code.split("-");
  return `${quarter} ${year.slice(2)}`;
}
