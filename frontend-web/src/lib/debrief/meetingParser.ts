/**
 * Standalone parser module for meeting extraction normalization and validation.
 * Extracts actionable tasks from raw AI output and ensures they match expected schema.
 */

// Mirrors ExtractedTaskJson in route.ts but strictly typed here
export type ExtractedTask = {
    raw_text?: string;
    title?: string;
    description?: string | null;
    brand_id?: string | null;
    role_slug?: string | null;
};

export type ValidatedTask = {
    rawText: string;
    title: string;
    description: string | null;
    brandId: string | null;
    roleSlug: string | null;
};

/**
 * Truncates meeting notes to the relevant "Next Steps" section if found.
 * This prevents processing thousands of tokens of transcript when only the summary matters.
 */
export const simplifyNotesForExtraction = (raw: string): string => {
    if (!raw) return "";
    const normalized = raw.replace(/\r\n/g, "\n");
    const headings = ["Suggested Next Steps:", "Suggested next steps:", "Next Steps:", "Action Items:"];

    for (const heading of headings) {
        const idx = normalized.indexOf(heading);
        if (idx !== -1) {
            // Keep valid context before heading (1500 chars)
            return normalized.slice(Math.max(0, idx - 1500));
        }
    }
    return normalized;
};

/**
 * Validates and normalizes raw AI JSON output into clean ValidatedTask objects.
 * Handles missing fields, nulls, whitespace, and type coercion.
 */
export const normalizeExtractedTasks = (tasks: unknown[]): ValidatedTask[] => {
    if (!Array.isArray(tasks)) return [];

    return tasks
        .map((task: any) => ({
            rawText: String(task?.raw_text ?? "").trim(),
            title: String(task?.title ?? "").trim(),
            description:
                task?.description === undefined || task?.description === null
                    ? null
                    : String(task.description).trim(),
            brandId: task?.brand_id ? String(task.brand_id).trim() : null,
            roleSlug: task?.role_slug ? String(task.role_slug).trim() : null,
        }))
        .filter((task) => task.title.length > 0);
};
