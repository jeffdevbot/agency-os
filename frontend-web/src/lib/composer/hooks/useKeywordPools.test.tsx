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
});
