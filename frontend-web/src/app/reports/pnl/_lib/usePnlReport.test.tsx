/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { usePnlReport } from "./usePnlReport";
import { getAccessToken } from "@/lib/getAccessToken";
import { getPnlReport, type PnlFilterMode, type PnlReport } from "./pnlApi";

vi.mock("@/lib/getAccessToken", () => ({
  getAccessToken: vi.fn(),
}));

vi.mock("./pnlApi", async () => {
  const actual = await vi.importActual<typeof import("./pnlApi")>("./pnlApi");
  return {
    ...actual,
    getPnlReport: vi.fn(),
  };
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function flushMicrotasks() {
  return new Promise((resolve) => {
    window.setTimeout(resolve, 0);
  });
}

async function renderHook(props: {
  profileId: string | null;
  filterMode?: PnlFilterMode;
  startMonth?: string;
  endMonth?: string;
}) {
  let hookValue: ReturnType<typeof usePnlReport>;
  const container = document.createElement("div");
  const root = createRoot(container);

  const Wrapper = ({
    profileId,
    filterMode = "ytd",
    startMonth,
    endMonth,
  }: {
    profileId: string | null;
    filterMode?: PnlFilterMode;
    startMonth?: string;
    endMonth?: string;
  }) => {
    hookValue = usePnlReport(profileId, filterMode, startMonth, endMonth);
    return null;
  };

  const render = async (nextProps: {
    profileId: string | null;
    filterMode?: PnlFilterMode;
    startMonth?: string;
    endMonth?: string;
  }) => {
    await act(async () => {
      root.render(<Wrapper {...nextProps} />);
    });
  };

  await render(props);

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
}

describe("usePnlReport", () => {
  beforeAll(() => {
    (globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(getAccessToken).mockResolvedValue("token");
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("ignores stale responses when filters change quickly", async () => {
    const firstRequest = deferred<PnlReport>();
    const secondRequest = deferred<PnlReport>();

    vi.mocked(getPnlReport)
      .mockImplementationOnce(() => firstRequest.promise)
      .mockImplementationOnce(() => secondRequest.promise);

    const hook = await renderHook({
      profileId: "profile-1",
      filterMode: "range",
      startMonth: "2026-01-01",
      endMonth: "2026-01-01",
    });

    await act(async () => {
      await flushMicrotasks();
    });

    await hook.rerender({
      profileId: "profile-1",
      filterMode: "range",
      startMonth: "2026-02-01",
      endMonth: "2026-02-01",
    });

    await act(async () => {
      await flushMicrotasks();
    });

    secondRequest.resolve({
      profile: {
        id: "profile-1",
        client_id: "client-1",
        marketplace_code: "US",
        currency_code: "USD",
        status: "active",
        notes: null,
        created_at: null,
        updated_at: null,
      },
      months: ["2026-02-01"],
      line_items: [],
      warnings: [],
    });

    await act(async () => {
      await secondRequest.promise;
      await flushMicrotasks();
    });

    expect(hook.result.report?.months).toEqual(["2026-02-01"]);
    expect(hook.result.errorMessage).toBeNull();

    firstRequest.resolve({
      profile: {
        id: "profile-1",
        client_id: "client-1",
        marketplace_code: "US",
        currency_code: "USD",
        status: "active",
        notes: null,
        created_at: null,
        updated_at: null,
      },
      months: ["2026-01-01"],
      line_items: [],
      warnings: [],
    });

    await act(async () => {
      await firstRequest.promise;
      await flushMicrotasks();
    });

    expect(hook.result.report?.months).toEqual(["2026-02-01"]);
    expect(getPnlReport).toHaveBeenCalledTimes(2);

    await hook.unmount();
  });
});
