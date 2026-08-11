import Link from "next/link";

import { ApiUnavailableError, fetchCompanies } from "@/lib/api";

import styles from "./page.module.css";

export default async function Home() {
  let companies;
  try {
    companies = await fetchCompanies();
  } catch (error) {
    return (
      <main className={styles.page}>
        <Masthead />
        <p className={styles.offline}>
          לא ניתן להגיע לשרת.{" "}
          <span className={styles.offlineDetail}>
            {error instanceof ApiUnavailableError ? error.message : String(error)}
          </span>
        </p>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <Masthead />

      <section>
        <h2 className={styles.sectionTitle}>חברות</h2>
        <ul className={styles.list}>
          {companies.map((company) => (
            <li key={company.id} className={styles.listItem}>
              <Link href={`/companies/${company.id}`} className={styles.listLink}>
                <span className={styles.companyName}>{company.legal_name}</span>
                <span className={styles.companyMeta}>
                  {company.sector}
                  <span className={styles.dot}>·</span>
                  <span className="ltr tnum">{company.id}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
        {companies.length === 0 && <p className={styles.empty}>עדיין לא נקלטו חברות.</p>}
      </section>
    </main>
  );
}

function Masthead() {
  return (
    <header className={styles.masthead}>
      <h1 className={styles.wordmark}>Report Intelligence</h1>
      <p className={styles.strapline}>
        דוח כספי, מתורגם לסיפור פיננסי שניתן לבדוק — כל מספר עם מקור.
      </p>
    </header>
  );
}
