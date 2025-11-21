/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import type { ComposerKeywordPool } from "@agency/lib/composer/types";
import { useKeywordPools } from "./useKeywordPools";

const mockFetchResponse = (payload: unknown, init?: { ok?: boolean; status?: number }) =>
  Promise.resolve({
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    json: () => Promise.resolve(payload),
  } as Response);

const flushMicrotasks = () => new Promise((resolve) => setTimeout(resolve, 0));
const getFetchMock = () => fetch as unknown as vi.Mock;

const renderHook = async (projectId?: string, groupId?: string | null) => {
  let hookValue: ReturnType<typeof useKeywordPools>;
  const container = document.createElement("div");
  const root = createRoot(container);

  const Wrapper = ({ pid, gid }: { pid?: string; gid?: string | null }) => {
    hookValue = useKeywordPools(pid, gid);
    return null;
  };

  const render = async (pid?: string, gid?: string | null) => {
    await act(async () => {
      root.render(<Wrapper pid={pid} gid={gid} />);
    });
  };

  await render(projectId, groupId);

  return {
    get result() {
      return hookValue!;
    },
    rerender: render,
    async unmount() {
      await act(async () => root.unmount());
    },
  };
};

describe("useKeywordPools", () => {
  const basePool: ComposerKeywordPool = {
    id: "pool-1",
    organizationId: "org-1",
    projectId: "proj-1",
    groupId: null,
    poolType: "body",
    status: "uploaded",
    rawKeywords: ["blue", "red"],
    cleanedKeywords: [],
    removedKeywords: [],
    cleanSettings: {},
    groupingConfig: {},
    cleanedAt: null,
    groupedAt: null,
    approvedAt: null,
    createdAt: "2025-01-01T00:00:00.000Z",
  };

  beforeAll(() => {
    (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads pools on mount for a project", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    expect(fetch).toHaveBeenCalledWith("/api/composer/projects/proj-1/keyword-pools");
    expect(hook.result.pools).toHaveLength(1);
    await hook.unmount();
  });

  it("uploads keywords and merges with existing pool", async () => {
    // initial load
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
    // upload response
    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, rawKeywords: ["blue", "red", "green"], id: "pool-1" },
      }),
    );

    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    await act(async () => {
      await hook.result.uploadKeywords("body", ["green"]);
      await flushMicrotasks();
    });

    const bodyPool = hook.result.pools.find((p) => p.poolType === "body");
    expect(bodyPool?.rawKeywords).toContain("green");
    await hook.unmount();
  });

  it("returns warning from upload response", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [] }));
    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, rawKeywords: ["one", "two", "three", "four", "five"] },
        warning: "low count",
      }),
    );

    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    let warning: string | undefined;
    await act(async () => {
      const result = await hook.result.uploadKeywords("body", ["one", "two", "three", "four", "five"]);
      warning = result.warning;
      await flushMicrotasks();
    });
    expect(warning).toBe("low count");
    await hook.unmount();
  });

  it("cleans and approves pools", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, cleanedKeywords: ["blue"], removedKeywords: [{ term: "red", reason: "color" }] },
      }),
    );
    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, status: "cleaned", cleanedAt: "2025-01-02T00:00:00.000Z" },
      }),
    );

    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    await act(async () => {
      await hook.result.cleanPool("pool-1", { removeColors: true });
      await flushMicrotasks();
    });
    expect(hook.result.pools[0].cleanedKeywords).toEqual(["blue"]);

    await act(async () => {
      await hook.result.approveClean("pool-1");
      await flushMicrotasks();
    });
    expect(hook.result.pools[0].status).toBe("cleaned");
    await hook.unmount();
  });

  it("handles errors and restores pools on upload failure", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
    getFetchMock().mockResolvedValueOnce(
      Promise.resolve({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ error: "bad" }),
      } as Response),
    );

    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    await act(async () => {
      await hook.result.uploadKeywords("body", ["green"]);
      await flushMicrotasks();
      await flushMicrotasks();
    });
    expect(hook.result.error).toBe("bad");
    // ensure optimistic state rolled back
    expect(hook.result.pools[0].rawKeywords).toEqual(["blue", "red"]);
    await hook.unmount();
  });

  it("supports manual remove and restore", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, cleanedKeywords: ["blue"], removedKeywords: [{ term: "red", reason: "manual" }] },
      }),
    );
    await act(async () => {
      await hook.result.manualRemove("pool-1", "red");
      await flushMicrotasks();
    });
    expect(hook.result.pools[0].removedKeywords).toHaveLength(1);

    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, cleanedKeywords: ["blue", "red"], removedKeywords: [] },
      }),
    );
    await act(async () => {
      await hook.result.manualRestore("pool-1", "red");
      await flushMicrotasks();
    });
    expect(hook.result.pools[0].cleanedKeywords).toContain("red");
    await hook.unmount();
  });

  it("deletes all keywords from a pool", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...basePool, rawKeywords: [], cleanedKeywords: [], removedKeywords: [], status: "uploaded" },
      }),
    );

    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    await act(async () => {
      await hook.result.deleteKeywords("pool-1");
      await flushMicrotasks();
    });

    expect(hook.result.pools[0].rawKeywords).toHaveLength(0);
    expect(hook.result.pools[0].cleanedKeywords).toHaveLength(0);
    await hook.unmount();
  });

  it("unapproves a cleaned pool", async () => {
    const cleanedPool = { ...basePool, status: "cleaned" as const, cleanedKeywords: ["blue"] };
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [cleanedPool] }));
    getFetchMock().mockResolvedValueOnce(
      mockFetchResponse({
        pool: { ...cleanedPool, status: "uploaded" },
      }),
    );

    const hook = await renderHook("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    await act(async () => {
      await hook.result.unapproveClean("pool-1");
      await flushMicrotasks();
    });

    expect(getFetchMock()).toHaveBeenLastCalledWith(
      "/api/composer/keyword-pools/pool-1",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "uploaded" }),
      },
    );
    expect(hook.result.pools[0].status).toBe("uploaded");
    await hook.unmount();
  });

  // Stage 7: Grouping Plan Tests
  describe("generateGroupingPlan", () => {
    it("generates grouping plan successfully", async () => {
      const cleanedPool = { ...basePool, status: "cleaned" as const, cleanedKeywords: ["blue", "red", "green"] };
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [cleanedPool] }));
      getFetchMock().mockResolvedValueOnce(
        mockFetchResponse({
          pool: {
            ...cleanedPool,
            groupingConfig: { basis: "single", groupCount: 1, phrasesPerGroup: 10 },
          },
        }),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      await act(async () => {
        await hook.result.generateGroupingPlan("pool-1", {
          basis: "single",
          groupCount: 1,
          phrasesPerGroup: 10,
        });
        await flushMicrotasks();
      });

      expect(getFetchMock()).toHaveBeenLastCalledWith(
        "/api/composer/keyword-pools/pool-1/grouping-plan",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            config: { basis: "single", groupCount: 1, phrasesPerGroup: 10 },
          }),
        },
      );
      expect(hook.result.pools[0].groupingConfig).toEqual({
        basis: "single",
        groupCount: 1,
        phrasesPerGroup: 10,
      });
      await hook.unmount();
    });

    it("handles grouping plan generation errors", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: "AI service unavailable" }),
        } as Response),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.generateGroupingPlan("pool-1", { basis: "custom" });
        await flushMicrotasks();
      });

      expect(result).toBeNull();
      expect(hook.result.error).toBe("AI service unavailable");
      await hook.unmount();
    });
  });

  describe("getGroups", () => {
    it("fetches groups with overrides successfully", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        mockFetchResponse({
          groups: [
            { id: "group-1", label: "Group 1", phrases: ["blue", "red"] },
            { id: "group-2", label: "Group 2", phrases: ["green"] },
          ],
          overrides: [
            { phrase: "red", action: "move", sourceGroupId: "group-1", targetGroupIndex: 1 },
          ],
        }),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.getGroups("pool-1");
        await flushMicrotasks();
      });

      expect(getFetchMock()).toHaveBeenLastCalledWith("/api/composer/keyword-pools/pool-1/groups");
      expect(result.groups).toHaveLength(2);
      expect(result.overrides).toHaveLength(1);
      expect(result.groups[0].phrases).toContain("blue");
      await hook.unmount();
    });

    it("handles getGroups errors", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ error: "Groups not found" }),
        } as Response),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.getGroups("pool-1");
        await flushMicrotasks();
      });

      expect(result).toBeNull();
      expect(hook.result.error).toBe("Groups not found");
      await hook.unmount();
    });
  });

  describe("addOverride", () => {
    it("tracks move override successfully", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ success: true }));

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: boolean;
      await act(async () => {
        result = await hook.result.addOverride("pool-1", {
          phrase: "blue",
          action: "move",
          sourceGroupId: "group-1",
          targetGroupLabel: "Group 2",
          targetGroupIndex: 1,
        });
        await flushMicrotasks();
      });

      expect(result).toBe(true);
      expect(getFetchMock()).toHaveBeenLastCalledWith(
        "/api/composer/keyword-pools/pool-1/group-overrides",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phrase: "blue",
            action: "move",
            sourceGroupId: "group-1",
            targetGroupLabel: "Group 2",
            targetGroupIndex: 1,
          }),
        },
      );
      await hook.unmount();
    });

    it("returns true even on override tracking failure (non-blocking)", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: "Database error" }),
        } as Response),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: boolean;
      await act(async () => {
        result = await hook.result.addOverride("pool-1", {
          phrase: "test",
          action: "remove",
        });
        await flushMicrotasks();
      });

      // Should still return true - override tracking is non-blocking
      expect(result).toBe(true);
      // Error should not be set for non-blocking operations
      expect(hook.result.error).toBeNull();
      await hook.unmount();
    });
  });

  describe("resetOverrides", () => {
    it("resets all overrides successfully", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ success: true }));

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: boolean;
      await act(async () => {
        result = await hook.result.resetOverrides("pool-1");
        await flushMicrotasks();
      });

      expect(result).toBe(true);
      expect(getFetchMock()).toHaveBeenLastCalledWith(
        "/api/composer/keyword-pools/pool-1/group-overrides",
        { method: "DELETE" },
      );
      await hook.unmount();
    });

    it("handles reset overrides errors", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: "Failed to reset" }),
        } as Response),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: boolean;
      await act(async () => {
        result = await hook.result.resetOverrides("pool-1");
        await flushMicrotasks();
      });

      expect(result).toBe(false);
      expect(hook.result.error).toBe("Failed to reset");
      await hook.unmount();
    });
  });

  describe("approveGrouping", () => {
    it("approves grouping and updates pool status", async () => {
      const cleanedPool = { ...basePool, status: "cleaned" as const, cleanedKeywords: ["blue", "red"] };
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [cleanedPool] }));
      getFetchMock().mockResolvedValueOnce(
        mockFetchResponse({
          pool: { ...cleanedPool, status: "grouped", groupedAt: "2025-01-03T00:00:00.000Z" },
        }),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.approveGrouping("pool-1");
        await flushMicrotasks();
      });

      expect(getFetchMock()).toHaveBeenLastCalledWith(
        "/api/composer/keyword-pools/pool-1/approve-grouping",
        { method: "POST" },
      );
      expect(result.status).toBe("grouped");
      expect(hook.result.pools[0].status).toBe("grouped");
      await hook.unmount();
    });

    it("handles approve grouping errors", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ error: "No groups to approve" }),
        } as Response),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.approveGrouping("pool-1");
        await flushMicrotasks();
      });

      expect(result).toBeNull();
      expect(hook.result.error).toBe("No groups to approve");
      await hook.unmount();
    });
  });

  describe("unapproveGrouping", () => {
    it("unapproves grouping and updates pool status", async () => {
      const groupedPool = { ...basePool, status: "grouped" as const, groupedAt: "2025-01-03T00:00:00.000Z" };
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [groupedPool] }));
      getFetchMock().mockResolvedValueOnce(
        mockFetchResponse({
          pool: { ...groupedPool, status: "cleaned", groupedAt: null },
        }),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.unapproveGrouping("pool-1");
        await flushMicrotasks();
      });

      expect(getFetchMock()).toHaveBeenLastCalledWith(
        "/api/composer/keyword-pools/pool-1?action=unapprove",
        { method: "DELETE" },
      );
      expect(result.status).toBe("cleaned");
      expect(hook.result.pools[0].status).toBe("cleaned");
      expect(hook.result.pools[0].groupedAt).toBeNull();
      await hook.unmount();
    });

    it("handles unapprove grouping errors", async () => {
      getFetchMock().mockResolvedValueOnce(mockFetchResponse({ pools: [basePool] }));
      getFetchMock().mockResolvedValueOnce(
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ error: "Pool not approved" }),
        } as Response),
      );

      const hook = await renderHook("proj-1");
      await act(async () => {
        await flushMicrotasks();
      });

      let result: any;
      await act(async () => {
        result = await hook.result.unapproveGrouping("pool-1");
        await flushMicrotasks();
      });

      expect(result).toBeNull();
      expect(hook.result.error).toBe("Pool not approved");
      await hook.unmount();
    });
  });
});
