/**
 * Shared keyword cleanup lexicons.
 * These lists are intentionally small; most filtering is data-driven from project inputs.
 */
export const STOP_WORDS = [
  "n/a",
  "na",
  "tbd",
  "none",
  "null",
];

// Fallback color lexicon used when attribute-derived colors are absent.
export const COLOR_LEXICON = [
  "red",
  "blue",
  "green",
  "black",
  "white",
  "silver",
  "gold",
  "pink",
  "yellow",
  "orange",
  "purple",
  "brown",
  "gray",
  "grey",
  "beige",
  "navy",
  "teal",
  "multi",
];

// Size/dimension patterns used as a fallback when attributes are unavailable.
export const SIZE_PATTERNS: RegExp[] = [
  /\b(?:xxs|xs|s|m|l|xl|xxl|xxxl)\b/i,
  /\b\d+\s?(?:cm|mm|in|inch|inches|ft|foot|feet)\b/i,
  /\b\d+(?:x|×)\d+(?:x|×)?\d*\b/i,
  /\b\d+\s?(?:pack|pk|count|ct)\b/i,
];
