import { CompanySearch } from "@/components/CompanySearch";
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
        {companies.length === 0 ? (
          <p className={styles.empty}>{t.ui.noCompanies}</p>
        ) : (
          <CompanySearch
            companies={companies}
            locale={locale}
            labels={{
              placeholder: t.ui.searchPlaceholder,
              ariaLabel: t.ui.searchLabel,
              noMatches: t.ui.noMatches,
              countAll: t.ui.searchCountAll,
              countFiltered: t.ui.searchCountFiltered,
            }}
          />
        )}
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
