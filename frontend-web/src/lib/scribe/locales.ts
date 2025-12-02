export const SUPPORTED_LOCALES = [
  "en-US",
  "en-CA",
  "en-GB",
  "en-AU",
  "fr-CA",
  "fr-FR",
  "es-MX",
  "es-ES",
  "de-DE",
  "it-IT",
  "pt-BR",
  "nl-NL",
] as const;

export type ScribeLocale = (typeof SUPPORTED_LOCALES)[number];

export const LOCALE_LABELS: Record<ScribeLocale, string> = {
  "en-US": "English (United States)",
  "en-CA": "English (Canada)",
  "en-GB": "English (United Kingdom)",
  "en-AU": "English (Australia)",
  "fr-CA": "French (Canada)",
  "fr-FR": "French (France)",
  "es-MX": "Spanish (Mexico)",
  "es-ES": "Spanish (Spain)",
  "de-DE": "German (Germany)",
  "it-IT": "Italian (Italy)",
  "pt-BR": "Portuguese (Brazil)",
  "nl-NL": "Dutch (Netherlands)",
};

export const isSupportedLocale = (value: string | undefined | null): value is ScribeLocale =>
  !!value && SUPPORTED_LOCALES.includes(value as ScribeLocale);
