import { describe, it, expect } from "vitest";
import { simplifyNotesForExtraction, normalizeExtractedTasks } from "../meetingParser";

describe("simplifyNotesForExtraction", () => {
    it("returns original text if no headings found", () => {
        const text = "Just some notes without action items.";
        expect(simplifyNotesForExtraction(text)).toBe(text);
    });

    it("returns slice starting 1500 chars before heading if heading found", () => {
        const prefix = "a".repeat(2000);
        const text = `${prefix}\nNext Steps:\n1. Do thing`;
        const result = simplifyNotesForExtraction(text);

        // It should contain the heading
        expect(result).toContain("Next Steps:");

        // It should be shorter than full text
        expect(result.length).toBeLessThan(text.length);

        // It should start roughly 1500 chars before the match
        // match index is 2000 + 1 (newline). 2001 - 1500 = 501.
        // So expected length is approx (2000 - 501) + len("Next Steps:...")
        expect(result.length).toBeGreaterThan(1500);
    });

    it("handles multiple headings by picking first occurrence", () => {
        const text = "Intro... Next Steps: 1. A... Action Items: 2. B";
        // 'Next Steps:' appears first.
        expect(simplifyNotesForExtraction(text)).toContain("Next Steps:");
    });

    it("handles empty input", () => {
        expect(simplifyNotesForExtraction("")).toBe("");
    });
});

describe("normalizeExtractedTasks", () => {
    it("handles valid full task", () => {
        const input = [{
            raw_text: "Do x",
            title: "Task X",
            description: "Desc",
            brand_id: "brand-123",
            role_slug: "dev"
        }];
        const result = normalizeExtractedTasks(input);
        expect(result).toHaveLength(1);
        expect(result[0]).toEqual({
            rawText: "Do x",
            title: "Task X",
            description: "Desc",
            brandId: "brand-123",
            roleSlug: "dev"
        });
    });

    it("handles missing optional fields", () => {
        const input = [{ title: "Task Y" }];
        const result = normalizeExtractedTasks(input);
        expect(result[0]).toEqual({
            rawText: "",
            title: "Task Y",
            description: null,
            brandId: null,
            roleSlug: null
        });
    });

    it("filters out validation failures (no title)", () => {
        const input = [
            { title: "" },
            { title: "   " },
            { description: "No title here" }
        ];
        expect(normalizeExtractedTasks(input)).toHaveLength(0);
    });

    it("coerces non-string types", () => {
        const input = [{
            title: 123,
            description: 456,
            brand_id: 789
        }];
        const result = normalizeExtractedTasks(input);
        expect(result[0]).toEqual({
            rawText: "",
            title: "123",
            description: "456",
            brandId: "789",
            roleSlug: null
        });
    });

    it("handles null/undefined input gracefully", () => {
        expect(normalizeExtractedTasks(null as any)).toEqual([]);
        expect(normalizeExtractedTasks(undefined as any)).toEqual([]);
    });

    it("trims whitespace", () => {
        const input = [{ title: "  Task  " }];
        expect(normalizeExtractedTasks(input)[0].title).toBe("Task");
    });
});
