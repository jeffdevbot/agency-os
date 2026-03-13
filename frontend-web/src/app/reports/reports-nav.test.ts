import { describe, expect, it } from "vitest";
import * as fs from "fs";
import * as path from "path";

describe("Reports navigation", () => {
  it("home page routes through the client-first reports hub", () => {
    const pagePath = path.resolve(__dirname, "page.tsx");
    const content = fs.readFileSync(pagePath, "utf-8");

    expect(content).toContain("ReportsClientHub");
    expect(content).not.toContain('href="/reports/wbr"');
  });
});
