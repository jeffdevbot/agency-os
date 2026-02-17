import { ValidatedTask } from "./meetingParser";

export type TaskQualityFlag = {
    index: number;
    issues: string[];
};

export type TaskReviewResult = {
    summary: {
        total: number;
        valid: number;
        dropped: number;
        flagged: number;
    };
    flags: TaskQualityFlag[];
    severity: "ok" | "warn" | "high_risk";
};

/**
 * Analyzes extracted tasks for quality issues.
 * Pure function: deterministic and no side effects.
 */
export const reviewExtractedTasks = (tasks: ValidatedTask[], droppedCount: number = 0): TaskReviewResult => {
    const flags: TaskQualityFlag[] = [];
    let validCount = 0;

    tasks.forEach((task, index) => {
        const issues: string[] = [];

        // Title checks
        if (task.title.length < 5) {
            issues.push("title_too_short");
        }

        // Description checks
        if (!task.description || task.description.length < 10) {
            // It's robust to allow empty descriptions, but we flag for quality review
            // if it's completely missing or very short, as better tasks have context.
            if (!task.description) issues.push("missing_description");
            else issues.push("description_too_short");
        }

        // Metadata checks
        if (!task.brandId) {
            issues.push("missing_brand_id");
        }
        if (!task.roleSlug) {
            issues.push("missing_role_slug");
        }

        if (issues.length > 0) {
            flags.push({ index, issues });
        }
        validCount++;
    });

    const total = validCount + droppedCount;
    const flaggedCount = flags.length;

    // Severity Logic
    let severity: "ok" | "warn" | "high_risk" = "ok";

    if (total === 0) {
        // No tasks at all matches "ok" (nothing broken), or maybe warn?
        // Let's say ok for now, assuming empty meeting might be valid.
        severity = "ok";
    } else {
        const dropRate = droppedCount / total;
        const flagRate = flaggedCount / total;

        if (dropRate > 0.5 || flagRate > 0.7) {
            severity = "high_risk";
        } else if (dropRate > 0.2 || flagRate > 0.3) {
            severity = "warn";
        }
    }

    return {
        summary: {
            total,
            valid: validCount,
            dropped: droppedCount,
            flagged: flaggedCount,
        },
        flags,
        severity,
    };
};
