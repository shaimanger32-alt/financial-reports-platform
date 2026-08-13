"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LOCALES, LOCALE_NAMES, type Locale, isLocale } from "@/lib/i18n";

import styles from "./LanguageSwitch.module.css";

/**
 * Switching language without losing your place.
 *
 * The locale is the first path segment, so swapping it keeps the reader on the
 * same company and period. Sending them back to the home page to change
 * language would make the second language feel like a separate site rather than
 * the same one.
 */
export function LanguageSwitch({ locale }: { locale: Locale }) {
  const pathname = usePathname();

  function pathIn(target: Locale): string {
    const segments = pathname.split("/");
    // segments[0] is the empty string before the leading slash.
    if (segments.length > 1 && isLocale(segments[1])) {
      segments[1] = target;
      return segments.join("/");
    }
    return `/${target}`;
  }

  return (
    <nav className={styles.switch} aria-label="Language">
      {LOCALES.map((option) => (
        <Link
          key={option}
          href={pathIn(option)}
          className={styles.option}
          hrefLang={option}
          aria-current={option === locale ? "true" : undefined}
          data-active={option === locale}
        >
          {LOCALE_NAMES[option]}
        </Link>
      ))}
    </nav>
  );
}
