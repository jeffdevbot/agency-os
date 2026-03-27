import { describe, expect, it } from "vitest";

import {
  FUTURE_SEARCH_TERM_AD_PRODUCTS,
  LIVE_SEARCH_TERM_AD_PRODUCT,
  SEARCH_TERM_AD_PRODUCTS,
} from "./searchTermProducts";

describe("searchTermProducts", () => {
  it("keeps Sponsored Products as the only live search-term ad product", () => {
    const liveProducts = SEARCH_TERM_AD_PRODUCTS.filter((product) => product.status === "live");
    expect(liveProducts).toHaveLength(1);
    expect(liveProducts[0]?.key).toBe("sp");
    expect(liveProducts[0]?.label).toBe("Sponsored Products");
    expect(LIVE_SEARCH_TERM_AD_PRODUCT.key).toBe("sp");
    expect(LIVE_SEARCH_TERM_AD_PRODUCT.shortLabel).toBe("SP");
    expect(LIVE_SEARCH_TERM_AD_PRODUCT.amazonAdsAdProduct).toBe("SPONSORED_PRODUCTS");
  });

  it("marks Sponsored Brands and Sponsored Display as future lanes", () => {
    expect(FUTURE_SEARCH_TERM_AD_PRODUCTS.map((product) => product.key)).toEqual(["sb", "sd"]);
    expect(FUTURE_SEARCH_TERM_AD_PRODUCTS.every((product) => product.status === "planned")).toBe(
      true,
    );
  });
});
