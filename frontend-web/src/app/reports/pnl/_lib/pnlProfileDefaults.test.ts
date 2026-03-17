import { describe, expect, it } from "vitest";

import { defaultPnlCurrencyCode } from "./pnlProfileDefaults";

describe("defaultPnlCurrencyCode", () => {
  it("returns CAD for CA marketplaces", () => {
    expect(defaultPnlCurrencyCode("CA")).toBe("CAD");
    expect(defaultPnlCurrencyCode("ca")).toBe("CAD");
  });

  it("returns USD for non-CA marketplaces", () => {
    expect(defaultPnlCurrencyCode("US")).toBe("USD");
    expect(defaultPnlCurrencyCode("")).toBe("USD");
  });
});
