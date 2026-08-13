import type { Metadata } from "next";
import { Assistant, Frank_Ruhl_Libre } from "next/font/google";
import { notFound } from "next/navigation";

import { LanguageSwitch } from "@/components/LanguageSwitch";
import { LOCALES, directionOf, getDictionary, isLocale } from "@/lib/i18n";

import "../globals.css";

const frank = Frank_Ruhl_Libre({
  subsets: ["hebrew", "latin"],
  weight: ["400", "500", "700"],
  variable: "--font-frank",
  display: "swap",
});

const assistant = Assistant({
  subsets: ["hebrew", "latin"],
  weight: ["300", "400", "600"],
  variable: "--font-assistant",
  display: "swap",
});

/**
 * Both languages are built at build time. There are two of them, and the set is
 * closed, so there is nothing to defer.
 */
export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata(props: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await props.params;
  if (!isLocale(locale)) return {};

  return {
    title: "Report Intelligence",
    description: getDictionary(locale).ui.tagline,
  };
}

/**
 * This is the root layout. `lang` and `dir` live here rather than a segment
 * above, because both depend on the locale and neither is cosmetic: a
 * right-to-left document puts English punctuation in the wrong place, and a
 * left-to-right one does the same to Hebrew.
 */
export default async function LocaleLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  // An unknown language is a 404 rather than a silent fall back to English.
  // Serving the wrong language at a URL that promised another is worse than
  // saying the page is not there.
  if (!isLocale(locale)) notFound();

  return (
    <html
      lang={locale}
      dir={directionOf(locale)}
      className={`${frank.variable} ${assistant.variable}`}
    >
      <body>
        <LanguageSwitch locale={locale} />
        {children}
      </body>
    </html>
  );
}
