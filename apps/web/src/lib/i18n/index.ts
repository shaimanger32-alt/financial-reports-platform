/**
 * Looking up wording for a language.
 *
 * There is deliberately no localisation library. Two languages, one dictionary
 * shape and a type error when a key is missing does everything a library would,
 * and adding a dependency for it would be the kind of "might be useful later"
 * this project declines.
 */

import type { Dictionary, Explanation, PatternMessage } from "./dictionary";
import { en } from "./en";
import { he } from "./he";
import type { Locale } from "./locale";

const DICTIONARIES: Record<Locale, Dictionary> = { en, he };

export function getDictionary(locale: Locale): Dictionary {
  return DICTIONARIES[locale];
}

/**
 * A signal's wording. Falls back to the key, which is ugly on purpose: a key on
 * screen is a visible bug, and a blank space is an invisible one.
 */
export function signalMessage(dictionary: Dictionary, key: string): string {
  return dictionary.signals[key] ?? key;
}

export function patternMessage(dictionary: Dictionary, key: string): PatternMessage {
  return dictionary.patterns[key] ?? { title: key, body: "" };
}

export function warningMessage(dictionary: Dictionary, code: string): string {
  return dictionary.warnings[code] ?? code;
}

export function explanationStatusLabel(dictionary: Dictionary, status: string): string {
  return dictionary.explanationStatus[status] ?? status;
}

export function explanationFor(dictionary: Dictionary, code: string): Explanation | undefined {
  return dictionary.metricExplanations[code] ?? dictionary.lineItemExplanations[code];
}

/** Why a figure is missing, said plainly rather than left blank (section 4.4). */
export function explainMissing(
  dictionary: Dictionary,
  warnings: string[],
  missingInputs: string[],
): string {
  if (warnings.length > 0) {
    return warningMessage(dictionary, warnings[0]);
  }
  if (missingInputs.length > 0) {
    return dictionary.ui.notReported(missingInputs.join(", "));
  }
  return dictionary.ui.notComputable;
}

export type { Dictionary, Explanation, PatternMessage } from "./dictionary";
export {
  DEFAULT_LOCALE,
  LOCALE_NAMES,
  LOCALES,
  directionOf,
  intlLocaleOf,
  isLocale,
  toLocale,
} from "./locale";
export type { Locale } from "./locale";
