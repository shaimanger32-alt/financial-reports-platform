import type { ReactNode } from "react";

import { CATEGORY_INTROS } from "@/lib/explanations";
import { CATEGORY_LABELS } from "@/lib/messages";

import styles from "./CategorySection.module.css";

/**
 * A group of metrics, closed until the reader wants it.
 *
 * Thirty-five figures at once is a spreadsheet, and spec section 26.2 asks for
 * six to eight cards rather than thirty. Grouping them behind a heading that
 * says what the group is *for* lets the page answer "how is this company doing"
 * first and "what exactly is the cash conversion cycle" only when asked.
 *
 * The count of available figures sits on the header on purpose: it is the
 * honest reason to open a section, and it makes a thin group visible before it
 * is opened rather than after.
 */
export function CategorySection({
  category,
  available,
  total,
  children,
  defaultOpen = false,
}: {
  category: string;
  available: number;
  total: number;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const intro = CATEGORY_INTROS[category];

  return (
    <details className={styles.section} open={defaultOpen}>
      <summary className={styles.header}>
        <span className={styles.marker} aria-hidden />
        <span className={styles.headings}>
          <span className={styles.title}>{CATEGORY_LABELS[category] ?? category}</span>
          {intro && <span className={styles.intro}>{intro}</span>}
        </span>
        <span className={styles.count}>
          <span className="tnum">{available}</span>
          {available < total && (
            <span className={styles.of}>
              {" "}
              מתוך <span className="tnum">{total}</span>
            </span>
          )}
        </span>
      </summary>
      <div className={styles.body}>{children}</div>
    </details>
  );
}
