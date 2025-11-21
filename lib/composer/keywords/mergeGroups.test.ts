import { describe, it, expect } from "vitest";
import type {
  ComposerKeywordGroup,
  ComposerKeywordGroupOverride,
} from "@agency/lib/composer/types";
import { mergeGroupsWithOverrides } from "./mergeGroups";

const buildGroup = (
  index: number,
  label: string,
  phrases: string[],
): ComposerKeywordGroup => ({
  id: `group-${index}`,
  organizationId: "org-123",
  keywordPoolId: "pool-123",
  groupIndex: index,
  label,
  phrases,
  metadata: {},
  createdAt: new Date().toISOString(),
});

const buildOverride = (
  action: "move" | "remove" | "add",
  phrase: string,
  targetIndex?: number,
  targetLabel?: string,
): ComposerKeywordGroupOverride => ({
  id: `override-${Math.random()}`,
  organizationId: "org-123",
  keywordPoolId: "pool-123",
  sourceGroupId: null,
  phrase,
  action,
  targetGroupLabel: targetLabel || null,
  targetGroupIndex: targetIndex ?? null,
  createdAt: new Date().toISOString(),
});

describe("mergeGroupsWithOverrides", () => {
  it("returns AI groups unchanged when no overrides", () => {
    const aiGroups = [
      buildGroup(0, "Blue Keywords", ["blue shirt", "navy pants"]),
      buildGroup(1, "Red Keywords", ["red dress", "crimson skirt"]),
    ];

    const result = mergeGroupsWithOverrides(aiGroups, []);

    expect(result).toHaveLength(2);
    expect(result[0].groupIndex).toBe(0);
    expect(result[0].label).toBe("Blue Keywords");
    expect(result[0].phrases).toEqual(["blue shirt", "navy pants"]);
    expect(result[1].groupIndex).toBe(1);
    expect(result[1].label).toBe("Red Keywords");
    expect(result[1].phrases).toEqual(["red dress", "crimson skirt"]);
  });

  it("removes a keyword from all groups when action is remove", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["keyword1", "keyword2", "keyword3"]),
      buildGroup(1, "Group B", ["keyword4", "keyword5"]),
    ];

    const overrides = [buildOverride("remove", "keyword2")];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result[0].phrases).toEqual(["keyword1", "keyword3"]);
    expect(result[1].phrases).toEqual(["keyword4", "keyword5"]);
  });

  it("moves a keyword from one group to another", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["keyword1", "keyword2", "keyword3"]),
      buildGroup(1, "Group B", ["keyword4", "keyword5"]),
    ];

    const overrides = [buildOverride("move", "keyword2", 1, "Group B")];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result[0].phrases).toEqual(["keyword1", "keyword3"]);
    expect(result[1].phrases).toEqual(["keyword4", "keyword5", "keyword2"]);
  });

  it("adds a new keyword to an existing group", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["keyword1", "keyword2"]),
      buildGroup(1, "Group B", ["keyword3"]),
    ];

    const overrides = [buildOverride("add", "new keyword", 0, "Group A")];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result[0].phrases).toEqual(["keyword1", "keyword2", "new keyword"]);
    expect(result[1].phrases).toEqual(["keyword3"]);
  });

  it("creates a new group when moving to non-existent index", () => {
    const aiGroups = [buildGroup(0, "Group A", ["keyword1", "keyword2"])];

    const overrides = [buildOverride("move", "keyword1", 2, "New Group")];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result).toHaveLength(2);
    expect(result[0].phrases).toEqual(["keyword2"]);
    expect(result[1].groupIndex).toBe(2);
    expect(result[1].label).toBe("New Group");
    expect(result[1].phrases).toEqual(["keyword1"]);
  });

  it("applies overrides in chronological order", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["keyword1", "keyword2", "keyword3"]),
      buildGroup(1, "Group B", ["keyword4"]),
    ];

    const overrides = [
      buildOverride("move", "keyword2", 1),
      buildOverride("move", "keyword2", 0),
    ];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result[0].phrases).toContain("keyword2");
    expect(result[1].phrases).not.toContain("keyword2");
  });

  it("handles case-insensitive keyword matching", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["Keyword1", "KEYWORD2", "keyword3"]),
    ];

    const overrides = [buildOverride("remove", "keyword2")];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result[0].phrases).toEqual(["Keyword1", "keyword3"]);
  });

  it("filters out groups with no phrases after overrides", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["keyword1"]),
      buildGroup(1, "Group B", ["keyword2", "keyword3"]),
    ];

    const overrides = [buildOverride("remove", "keyword1")];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result).toHaveLength(1);
    expect(result[0].groupIndex).toBe(1);
  });

  it("does not add duplicate keywords to target group", () => {
    const aiGroups = [
      buildGroup(0, "Group A", ["keyword1"]),
      buildGroup(1, "Group B", ["keyword2"]),
    ];

    const overrides = [
      buildOverride("move", "keyword1", 1),
      buildOverride("add", "keyword1", 1),
    ];

    const result = mergeGroupsWithOverrides(aiGroups, overrides);

    expect(result).toHaveLength(1);
    expect(result[0].groupIndex).toBe(1);
    expect(result[0].phrases).toEqual(["keyword2", "keyword1"]);
  });

  it("handles empty AI groups list", () => {
    const overrides = [buildOverride("add", "new keyword", 0, "New Group")];

    const result = mergeGroupsWithOverrides([], overrides);

    expect(result).toHaveLength(1);
    expect(result[0].groupIndex).toBe(0);
    expect(result[0].phrases).toEqual(["new keyword"]);
  });

  it("maintains group index order in results", () => {
    const aiGroups = [
      buildGroup(2, "Group C", ["keyword1"]),
      buildGroup(0, "Group A", ["keyword2"]),
      buildGroup(1, "Group B", ["keyword3"]),
    ];

    const result = mergeGroupsWithOverrides(aiGroups, []);

    expect(result[0].groupIndex).toBe(0);
    expect(result[1].groupIndex).toBe(1);
    expect(result[2].groupIndex).toBe(2);
  });
});
