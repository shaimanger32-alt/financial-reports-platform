"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { CompanySummary } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

import styles from "./CompanySearch.module.css";

/**
 * Finding a company.
 *
 * Filtering happens in the browser, over the list the page already fetched.
 * That is a deliberate call about scale rather than laziness: there are 42
 * published companies, the whole list is a few kilobytes, and a search endpoint
 * would add a round trip, a rate limit and a relevance-ranking question to solve
 * a problem that does not exist yet. When the list is thousands, this becomes a
 * server query — and the component's shape does not have to change for that.
 *
 * Matching is on name and on identifier, because a reader who knows a CIK or a
 * registrar number should not have to remember how the company spells itself.
 *
 * It takes plain strings rather than the dictionary. The dictionary holds
 * functions for the wording that needs them, and a React Server Component may
 * not pass a function into a client component — so the boundary carries only
 * what is rendered here.
 */
export interface SearchLabels {
  placeholder: string;
  ariaLabel: string;
  noMatches: string;
  countAll: string;
  countFiltered: string;
}

export function CompanySearch({
  companies,
  locale,
  labels,
}: {
  companies: CompanySummary[];
  locale: Locale;
  labels: SearchLabels;
}) {
  const [query, setQuery] = useState("");

  const nameOf = (company: CompanySummary) =>
    locale === "he" ? company.legal_name : (company.name_en ?? company.legal_name);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return companies;
    return companies.filter((company) =>
      [company.legal_name, company.name_en, company.id, company.sector]
        .filter((field): field is string => Boolean(field))
        .some((field) => field.toLowerCase().includes(needle)),
    );
  }, [companies, query]);

  return (
    <>
      <div className={styles.field}>
        <input
          type="search"
          className={styles.input}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={labels.placeholder}
          aria-label={labels.ariaLabel}
          autoComplete="off"
        />
        <span className={styles.count} aria-live="polite">
          {(matches.length === companies.length ? labels.countAll : labels.countFiltered)
            .replace("{shown}", String(matches.length))
            .replace("{total}", String(companies.length))}
        </span>
      </div>

      <ul className={styles.list}>
        {matches.map((company) => (
          <li key={company.id} className={styles.listItem}>
            <Link href={`/${locale}/companies/${company.id}`} className={styles.listLink}>
              {/* The legal name is the company's own. It is never translated. */}
              <span className={`${styles.companyName} name`}>{nameOf(company)}</span>
              <span className={styles.companyMeta}>
                {company.sector}
                {company.sector && <span className={styles.dot}>·</span>}
                <span className="ltr tnum">{company.id}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>

      {matches.length === 0 && <p className={styles.empty}>{labels.noMatches}</p>}
    </>
  );
}
