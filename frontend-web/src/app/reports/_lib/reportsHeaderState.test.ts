import { describe, expect, it } from "vitest";
import { buildReportsHeaderState } from "./reportsHeaderState";

describe("buildReportsHeaderState", () => {
  it("builds a marketplace switcher for Monthly P&L routes", () => {
    const state = buildReportsHeaderState("/reports/acme/us/pnl");

    expect(state.subtitle).toBe("Acme / US");
    expect(state.surfaceLinks).toEqual([
      { href: "/reports/acme/us/wbr", label: "WBR", active: false },
      { href: "/reports/acme/us/pnl", label: "Monthly P&L", active: true },
    ]);
    expect(state.actionLinks).toEqual([
      { href: "/reports/acme", label: "Client Hub" },
      { href: "/", label: "Back to Tools" },
    ]);
  });

  it("keeps WBR actions on WBR sync routes", () => {
    const state = buildReportsHeaderState("/reports/acme/ca/wbr/sync");

    expect(state.surfaceLinks[0]?.active).toBe(true);
    expect(state.actionLinks).toEqual([
      { href: "/reports/acme/ca/wbr", label: "Report", active: false },
      { href: "/reports/acme/ca/wbr/settings", label: "Settings", active: false },
      { href: "/reports/acme/ca/wbr/sync", label: "Sync", active: true },
      { href: "/reports/acme", label: "Client Hub" },
      { href: "/", label: "Back to Tools" },
    ]);
  });

  it("builds the client data access header for a specific client", () => {
    const state = buildReportsHeaderState("/reports/client-data-access/acme");

    expect(state.subtitle).toBe("Client Data Access / Acme");
    expect(state.actionLinks).toEqual([
      { href: "/reports", label: "Clients" },
      { href: "/reports/client-data-access", label: "Client Data Access" },
      { href: "/reports/acme", label: "Client Hub" },
      { href: "/", label: "Back to Tools" },
    ]);
  });
});
