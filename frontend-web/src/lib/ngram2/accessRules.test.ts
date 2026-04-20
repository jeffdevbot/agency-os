import { describe, expect, it } from "vitest";

import {
  canAccessNgram2,
  collectAssignedClientIds,
  hasAllowedTool,
  NGRAM2_TOOL_SLUG,
  normalizeAllowedTools,
} from "./accessRules";

describe("ngram2 access rules", () => {
  it("normalizes allowed tool slugs", () => {
    expect(normalizeAllowedTools([" NGRAM-2 ", "ngram-2", "scribe", "", 1])).toEqual([
      "ngram-2",
      "scribe",
    ]);
  });

  it("checks direct tool access", () => {
    expect(hasAllowedTool(["scribe", "ngram-2"], NGRAM2_TOOL_SLUG)).toBe(true);
    expect(hasAllowedTool(["scribe"], NGRAM2_TOOL_SLUG)).toBe(false);
  });

  it("treats admins as implicitly allowed", () => {
    expect(canAccessNgram2({ isAdmin: true, allowedTools: [] })).toBe(true);
    expect(canAccessNgram2({ isAdmin: false, allowedTools: ["ngram-2"] })).toBe(true);
    expect(canAccessNgram2({ isAdmin: false, allowedTools: ["scribe"] })).toBe(false);
  });

  it("collects unique assigned client ids for a team member", () => {
    expect(
      collectAssignedClientIds(
        [
          { clientId: "client-1", teamMemberId: "member-1" },
          { clientId: "client-1", teamMemberId: "member-1" },
          { clientId: "client-2", teamMemberId: "member-1" },
          { clientId: "client-3", teamMemberId: "member-2" },
        ],
        "member-1",
      ),
    ).toEqual(["client-1", "client-2"]);
  });
});
