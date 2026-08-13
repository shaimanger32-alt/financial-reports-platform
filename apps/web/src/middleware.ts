import { NextResponse, type NextRequest } from "next/server";

import { DEFAULT_LOCALE, LOCALES } from "@/lib/i18n";

/**
 * Every page lives under a language. A URL without one is sent to the reader's
 * own, when their browser states a preference we serve, and to English
 * otherwise.
 *
 * `Accept-Language` is a hint, never a decision: the language is always visible
 * in the URL afterwards, so a reader who wanted the other one can see what they
 * were given and change it in one click.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const hasLocale = LOCALES.some(
    (locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`),
  );
  if (hasLocale) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = `/${preferredLocale(request)}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

function preferredLocale(request: NextRequest): string {
  const header = request.headers.get("accept-language") ?? "";
  for (const entry of header.split(",")) {
    const tag = entry.split(";")[0].trim().toLowerCase();
    const language = tag.split("-")[0];
    const match = LOCALES.find((locale) => locale === language);
    if (match) return match;
  }
  return DEFAULT_LOCALE;
}

export const config = {
  // Everything except Next's own assets and files with an extension.
  matcher: ["/((?!_next|api|.*\\.).*)"],
};
