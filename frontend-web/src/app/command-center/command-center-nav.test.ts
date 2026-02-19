/**
 * Navigation test for Command Center home page (C6B.1).
 *
 * Validates that the ClickUp Spaces link is present in the
 * Command Center home page module.
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

describe("Command Center navigation", () => {
    it('home page contains ClickUp Spaces link to /command-center/clickup-spaces', () => {
        // Read the Command Center home page source to verify the link is present.
        // This avoids needing jsdom/RTL for a simple static content check.
        const pagePath = path.resolve(
            __dirname,
            "page.tsx",
        );
        const content = fs.readFileSync(pagePath, "utf-8");

        // Verify the href is present
        expect(content).toContain('/command-center/clickup-spaces');
        // Verify the label is present
        expect(content).toContain('ClickUp Spaces');
    });

    it('ClickUp Spaces link uses the same styling as other nav links', () => {
        const pagePath = path.resolve(
            __dirname,
            "page.tsx",
        );
        const content = fs.readFileSync(pagePath, "utf-8");

        // Count occurrences of the nav card CSS class pattern
        const navCardClass = 'rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg';
        const matches = content.split(navCardClass).length - 1;

        // Should have 5 nav cards: Clients, Team, Tokens, Admin, ClickUp Spaces
        expect(matches).toBe(5);
    });
});
