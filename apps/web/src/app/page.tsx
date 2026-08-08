import { fetchHealth, getApiBaseUrl } from "@/lib/api";

import styles from "./page.module.css";

/**
 * Phase 0 verification page.
 *
 * Its only job is to prove the exit criterion from spec section 39: the web app
 * can reach the API, and the API can reach the database. It is replaced by the
 * real home screen in phase 5.
 */
export default async function Page() {
  const probe = await fetchHealth();

  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <h1 className={styles.title}>Report Intelligence</h1>
        <p className={styles.subtitle}>
          בדיקת תקינות תשתית — שלב 0. אין כאן עדיין נתונים פיננסיים.
        </p>
      </header>

      <section className={styles.card}>
        <h2 className={styles.cardTitle}>מצב המערכת</h2>

        {probe.reachable ? (
          <dl className={styles.list}>
            <Row
              label="שרת ה-API"
              value={probe.health.status === "ok" ? "תקין" : "פועל, אך מדווח על תקלה"}
              ok={probe.health.status === "ok"}
            />
            <Row
              label="בסיס הנתונים"
              value={probe.health.database === "ok" ? "מחובר" : "לא מגיב"}
              ok={probe.health.database === "ok"}
            />
            <Row label="גרסה" value={probe.health.version} />
            <Row label="סביבה" value={probe.health.environment} />
            {probe.health.detail ? (
              <Row label="פירוט" value={probe.health.detail} ok={false} />
            ) : null}
          </dl>
        ) : (
          <div className={styles.errorBox}>
            <p className={styles.errorTitle}>לא ניתן להגיע ל-API</p>
            <p className={styles.errorDetail}>{probe.error}</p>
            <p className={styles.hint}>
              הפעל את השרת עם <code className={styles.code}>make api</code> ובדוק ש-
              <code className={styles.code}>API_BASE_URL</code> מצביע ל-{getApiBaseUrl()}.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

function Row({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  const valueClass =
    ok === undefined
      ? styles.value
      : ok
        ? `${styles.value} ${styles.ok}`
        : `${styles.value} ${styles.bad}`;

  return (
    <div className={styles.row}>
      <dt className={styles.label}>{label}</dt>
      <dd className={valueClass}>{value}</dd>
    </div>
  );
}
