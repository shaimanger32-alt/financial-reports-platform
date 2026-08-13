import Link from "next/link";

import { ApiUnavailableError, fetchCompanies } from "@/lib/api";
import { getDictionary, toLocale } from "@/lib/i18n";

import styles from "./page.module.css";

export default async function Home({ params }: PageProps<"/[locale]">) {
  const locale = toLocale((await params).locale);
  const t = getDictionary(locale);

  let companies;
  try {
    companies = await fetchCompanies();
  } catch (error) {
    return (
      <main className={styles.page}>
        <Masthead strapline={t.ui.strapline} />
        <p className={styles.offline}>
          {t.ui.serverUnreachable}{" "}
          <span className={styles.offlineDetail}>
            {error instanceof ApiUnavailableError ? error.message : String(error)}
          </span>
        </p>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <Masthead strapline={t.ui.strapline} />

      <section>
        <h2 className={styles.sectionTitle}>{t.ui.companies}</h2>
        <ul className={styles.list}>
          {companies.map((company) => (
            <li key={company.id} className={styles.listItem}>
              <Link href={`/${locale}/companies/${company.id}`} className={styles.listLink}>
                {/* The legal name is the company's own, in its own language.
                    It is never translated: it is what the filing says. */}
                <span className={`${styles.companyName} name`}>
                  {locale === "he" ? company.legal_name : (company.name_en ?? company.legal_name)}
                </span>
                <span className={styles.companyMeta}>
                  {company.sector}
                  {company.sector && <span className={styles.dot}>·</span>}
                  <span className="ltr tnum">{company.id}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
        {companies.length === 0 && <p className={styles.empty}>{t.ui.noCompanies}</p>}
      </section>
    </main>
  );
}

function Masthead({ strapline }: { strapline: string }) {
  return (
    <header className={styles.masthead}>
      <h1 className={styles.wordmark}>Report Intelligence</h1>
      <p className={styles.strapline}>{strapline}</p>
    </header>
  );
}
