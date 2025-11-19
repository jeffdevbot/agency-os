/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import type { ComposerSkuGroup } from "@agency/lib/composer/types";
import { useSkuGroups } from "./useSkuGroups";

const mockFetchResponse = (payload: unknown, init?: { ok?: boolean; status?: number }) =>
  Promise.resolve({
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    json: () => Promise.resolve(payload),
  } as Response);

const flushMicrotasks = () => new Promise((resolve) => setTimeout(resolve, 0));
const getFetchMock = () => fetch as unknown as vi.Mock;

const renderUseSkuGroups = async (projectId?: string) => {
  let hookValue: ReturnType<typeof useSkuGroups>;
  const container = document.createElement("div");
  const root = createRoot(container);

  const Wrapper = ({ pid }: { pid?: string }) => {
    hookValue = useSkuGroups(pid);
    return null;
  };

  const render = async (pid?: string) => {
    await act(async () => {
      root.render(<Wrapper pid={pid} />);
    });
  };

  await render(projectId);

  return {
    get result() {
      return hookValue!;
    },
    rerender: render,
    async unmount() {
      await act(async () => {
        root.unmount();
      });
    },
  };
};

describe("useSkuGroups", () => {
  const mockGroup: ComposerSkuGroup = {
    id: "group-1",
    organizationId: "org-1",
    projectId: "proj-1",
    name: "Group 1",
    description: "Desc",
    sortOrder: 0,
    createdAt: "2025-01-01T00:00:00.000Z",
  };

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

  it("loads groups on mount and updates loading state", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ groups: [mockGroup] }));
    const hook = await renderUseSkuGroups("proj-1");

    await act(async () => {
      await flushMicrotasks();
    });

    expect(fetch).toHaveBeenCalledWith("/api/composer/projects/proj-1/groups");
    expect(hook.result.groups).toEqual([mockGroup]);
    expect(hook.result.isLoading).toBe(false);
    await hook.unmount();
  });

  it("supports create, update, and delete flows", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ groups: [mockGroup] }));
    const hook = await renderUseSkuGroups("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    const newGroup = { ...mockGroup, id: "group-2", name: "Group 2" };
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ group: newGroup }));
    await act(async () => {
      await hook.result.createGroup("Group 2", "copy");
      await flushMicrotasks();
    });
    expect(hook.result.groups).toHaveLength(2);

    const updatedGroup = { ...newGroup, name: "Updated" };
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ group: updatedGroup }));
    await act(async () => {
      await hook.result.updateGroup(updatedGroup.id, { name: "Updated" });
      await flushMicrotasks();
    });
    expect(hook.result.groups.find((g) => g.id === updatedGroup.id)?.name).toBe("Updated");

    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ success: true }));
    await act(async () => {
      await hook.result.deleteGroup(updatedGroup.id);
      await flushMicrotasks();
    });
    expect(hook.result.groups).toEqual([mockGroup]);

    await hook.unmount();
  });

  it("returns early when projectId is missing", async () => {
    const hook = await renderUseSkuGroups(undefined);
    await act(async () => {
      await hook.result.refresh();
    });
    expect(fetch).not.toHaveBeenCalled();
    const created = await hook.result.createGroup("Group");
    expect(created).toBeNull();
    await hook.unmount();
  });

  it("propagates errors from assign/unassign and surfaces messages", async () => {
    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ groups: [mockGroup] }));
    const hook = await renderUseSkuGroups("proj-1");
    await act(async () => {
      await flushMicrotasks();
    });

    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ error: "nope" }, { ok: false, status: 400 }));
    await act(async () => {
      await expect(hook.result.assignToGroup("group-1", ["var-1"])).rejects.toThrow();
    });
    await act(async () => {
      await flushMicrotasks();
    });
    expect(hook.result.error).toBe("nope");

    getFetchMock().mockResolvedValueOnce(mockFetchResponse({ error: "fail" }, { ok: false, status: 400 }));
    await act(async () => {
      await expect(hook.result.unassignVariants(["var-1"])).rejects.toThrow();
    });
    await act(async () => {
      await flushMicrotasks();
    });
    expect(hook.result.error).toBe("fail");

    await hook.unmount();
  });
});
beforeAll(() => {
  (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
});
