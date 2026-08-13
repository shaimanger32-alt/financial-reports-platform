/**
 * The languages the product speaks.
 *
 * English leads because the companies do: the published set is American, filed
 * with the SEC in English. Hebrew is not a translation afterthought — it is the
 * language the product was written in first, and the market it returns to.
 *
 * Direction travels with the language rather than being set once on the
 * document. A Hebrew page is right to left and an English page is left to
 * right, and every number inside either is left to right regardless, which is
 * what the `ltr` utility class in globals.css is for.
 */

export const LOCALES = ["en", "he"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

/** Falls back rather than throwing: an unknown segment is a 404's business. */
export function toLocale(value: string | undefined): Locale {
  return value && isLocale(value) ? value : DEFAULT_LOCALE;
}

export function directionOf(locale: Locale): "ltr" | "rtl" {
  return locale === "he" ? "rtl" : "ltr";
}

/**
 * The BCP 47 tag `Intl` should format with.
 *
 * `en-US` rather than `en`, because the two disagree on nothing here but the
 * explicit tag documents which conventions a figure is being rendered in.
 */
export function intlLocaleOf(locale: Locale): string {
  return locale === "he" ? "he-IL" : "en-US";
}

export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  he: "עברית",
};
