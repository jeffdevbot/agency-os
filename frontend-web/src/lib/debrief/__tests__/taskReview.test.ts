import { describe, it, expect } from "vitest";
import { reviewExtractedTasks, TaskReviewResult } from "../taskReview";
import { ValidatedTask } from "../meetingParser";

describe("reviewExtractedTasks", () => {
    const mockTask = (overrides: Partial<ValidatedTask> = {}): ValidatedTask => ({
        rawText: "raw",
        title: "Valid Title Here",
        description: "Valid description here",
        brandId: "brand-123",
        roleSlug: "dev",
        ...overrides,
    });

    it("returns ok for perfect tasks", () => {
        const tasks = [mockTask(), mockTask()];
        const result = reviewExtractedTasks(tasks);

        expect(result.severity).toBe("ok");
        expect(result.summary.flagged).toBe(0);
        expect(result.flags).toHaveLength(0);
    });

    it("flags short titles", () => {
        const tasks = [mockTask({ title: "Tiny" })];
        const result = reviewExtractedTasks(tasks);

        expect(result.flags).toHaveLength(1);
        expect(result.flags[0].issues).toContain("title_too_short");
    });

    it("flags missing descriptions", () => {
        const tasks = [mockTask({ description: null })];
        const result = reviewExtractedTasks(tasks);

        expect(result.flags).toHaveLength(1);
        expect(result.flags[0].issues).toContain("missing_description");
    });

    it("flags missing metadata", () => {
        const tasks = [mockTask({ brandId: null, roleSlug: null })];
        const result = reviewExtractedTasks(tasks);

        expect(result.flags[0].issues).toContain("missing_brand_id");
        expect(result.flags[0].issues).toContain("missing_role_slug");
    });

    it("calculates high_risk severity for many issues", () => {
        // 2 tasks, both perfectly bad
        const tasks = [
            mockTask({ title: "Bad", description: null, brandId: null }),
            mockTask({ title: "Worse", description: null, brandId: null }),
        ];
        const result = reviewExtractedTasks(tasks);

        expect(result.severity).toBe("high_risk");
        expect(result.summary.flagged).toBe(2);
    });

    it("calculates warn severity for some issues", () => {
        // 3 tasks: 1 bad, 2 good. Flag rate 33% -> warn (threshold > 0.3)
        const tasks = [
            mockTask({ title: "Bad", description: null }),
            mockTask(),
            mockTask(),
        ];
        const result = reviewExtractedTasks(tasks);

        expect(result.severity).toBe("warn");
    });

    it("accounts for dropped tasks in total count", () => {
        const tasks = [mockTask()];
        // 1 valid, 10 dropped -> high drop rate
        const result = reviewExtractedTasks(tasks, 10);

        expect(result.summary.total).toBe(11);
        expect(result.summary.dropped).toBe(10);
        expect(result.severity).toBe("high_risk");
    });

    it("handles empty input", () => {
        const result = reviewExtractedTasks([]);
        expect(result.severity).toBe("ok");
        expect(result.summary.total).toBe(0);
    });
});
