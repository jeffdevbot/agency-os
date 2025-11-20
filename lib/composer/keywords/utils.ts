/**
 * Keyword Pipeline Utilities
 *
 * Helper functions for keyword deduplication, merging, CSV parsing, and validation.
 */

/**
 * Deduplicate keywords (case-insensitive, preserves first occurrence).
 * Trims whitespace from each keyword.
 *
 * @param keywords - Array of keyword strings
 * @returns Deduplicated array of trimmed keywords
 */
export function dedupeKeywords(keywords: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const keyword of keywords) {
    const trimmed = keyword.trim();
    if (!trimmed) continue; // Skip empty strings

    const normalized = trimmed.toLowerCase();
    if (!seen.has(normalized)) {
      seen.add(normalized);
      result.push(trimmed);
    }
  }

  return result;
}

/**
 * Merge two keyword arrays, deduplicating the result.
 * Existing keywords take precedence (appear first in output).
 *
 * @param existing - Current keywords array
 * @param incoming - New keywords to merge in
 * @returns Merged and deduplicated array
 */
export function mergeKeywords(existing: string[], incoming: string[]): string[] {
  const combined = [...existing, ...incoming];
  return dedupeKeywords(combined);
}

/**
 * Parse keywords from CSV content.
 * Supports single-column CSV with optional "keyword" header.
 * Handles UTF-8 encoding, trims whitespace, skips empty lines.
 *
 * @param csv - CSV string content
 * @returns Array of parsed keywords
 */
export function parseKeywordsCsv(csv: string): string[] {
  if (!csv || !csv.trim()) {
    return [];
  }

  const lines = csv.split(/\r?\n/);
  const keywords: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Skip empty lines
    if (!line) continue;

    // Skip header row if it exists (case-insensitive check)
    if (i === 0 && line.toLowerCase() === 'keyword') continue;
    if (i === 0 && line.toLowerCase().startsWith('"keyword"')) continue;

    // Remove surrounding quotes if present
    let keyword = line;
    if ((keyword.startsWith('"') && keyword.endsWith('"')) ||
        (keyword.startsWith("'") && keyword.endsWith("'"))) {
      keyword = keyword.slice(1, -1);
    }

    const trimmed = keyword.trim();
    if (trimmed) {
      keywords.push(trimmed);
    }
  }

  return keywords;
}

/**
 * Validate keyword count against min/max constraints.
 * Min: 5 keywords (hard requirement)
 * Max: 5000 keywords (hard requirement)
 * Warning: <20 keywords (soft warning)
 *
 * @param keywords - Array of keywords to validate
 * @returns Validation result with optional error message
 */
export function validateKeywordCount(keywords: string[]): {
  valid: boolean;
  error?: string;
  warning?: string;
} {
  const count = keywords.length;

  if (count < 5) {
    return {
      valid: false,
      error: `At least 5 keywords are required. You have ${count}.`,
    };
  }

  if (count > 5000) {
    return {
      valid: false,
      error: `Maximum 5000 keywords allowed. You have ${count}.`,
    };
  }

  if (count < 20) {
    return {
      valid: true,
      warning: `You have only ${count} keywords. For best results, we recommend 50-100+ keywords.`,
    };
  }

  return { valid: true };
}
