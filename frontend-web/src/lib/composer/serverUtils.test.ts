import { describe, expect, it } from "vitest";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";
import { isUuid, resolveComposerOrgIdFromSession } from "./serverUtils";

describe("isUuid", () => {
  it("returns true for valid UUIDs", () => {
    expect(isUuid("123e4567-e89b-12d3-a456-426614174000")).toBe(true);
  });

  it("returns false for invalid values", () => {
    expect(isUuid("not-a-uuid")).toBe(false);
    expect(isUuid(null)).toBe(false);
    expect(isUuid(undefined)).toBe(false);
  });
});

describe("resolveComposerOrgIdFromSession", () => {
  const baseSession = {
    user: {
      id: "user-1",
      app_metadata: {},
      user_metadata: {},
    },
  } as any;

  it("prefers the direct org_id field", () => {
    const session = {
      ...baseSession,
      user: { ...baseSession.user, org_id: "org-direct" },
    };
    expect(resolveComposerOrgIdFromSession(session)).toBe("org-direct");
  });

  it("falls back to metadata fields", () => {
    const session = {
      ...baseSession,
      user: {
        ...baseSession.user,
        app_metadata: { org_id: "org-app" },
      },
    };
    expect(resolveComposerOrgIdFromSession(session)).toBe("org-app");
  });

  it("uses default org when fallback is allowed", () => {
    expect(
      resolveComposerOrgIdFromSession(baseSession, { fallbackToDefault: true }),
    ).toBe(DEFAULT_COMPOSER_ORG_ID);
  });

  it("returns null when no org metadata is present and fallback is disabled", () => {
    expect(resolveComposerOrgIdFromSession(baseSession)).toBeNull();
  });
});
