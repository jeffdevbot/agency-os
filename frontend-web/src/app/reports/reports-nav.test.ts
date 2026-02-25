import { describe, expect, it } from "vitest";
import * as fs from "fs";
import * as path from "path";

describe("Reports navigation", () => {
  it("home page contains WBR and Setup New WBR links", () => {
    const pagePath = path.resolve(__dirname, "page.tsx");
    const content = fs.readFileSync(pagePath, "utf-8");

    expect(content).toContain('href="/reports/wbr"');
    expect(content).toContain("WBR");
    expect(content).toContain('href="/reports/wbr/setup"');
    expect(content).toContain("Setup New WBR");
  });
});
