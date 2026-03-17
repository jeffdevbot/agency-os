import { describe, expect, it } from "vitest";

import {
  buildSection2DisplayRows,
  formatSection2MetricValue,
} from "./wbrSection2RowDisplay";
import type { WbrSection2Row } from "../wbr/_lib/wbrSection1Api";

const makeRow = (overrides: Partial<WbrSection2Row>): WbrSection2Row => ({
  id: "row-1",
  row_label: "Parent Row",
  row_kind: "parent",
  parent_row_id: null,
  sort_order: 1,
  weeks: [
    {
      impressions: 100,
      clicks: 10,
      ctr_pct: 0.1,
      ad_spend: "25.00",
      cpc: "2.50",
      ad_orders: 2,
      ad_conversion_rate: 0.2,
      ad_sales: "80.00",
      acos_pct: 0.3125,
      business_sales: "100.00",
      tacos_pct: 0.25,
      tacos_available: true,
    },
  ],
  ad_type_breakdown: [
    {
      ad_type: "sponsored_products",
      label: "Sponsored Products",
      weeks: [
        {
          impressions: 60,
          clicks: 6,
          ctr_pct: 0.1,
          ad_spend: "15.00",
          cpc: "2.50",
          ad_orders: 1,
          ad_conversion_rate: 1 / 6,
          ad_sales: "40.00",
          acos_pct: 0.375,
          business_sales: "0.00",
          tacos_pct: null,
          tacos_available: false,
        },
      ],
    },
    {
      ad_type: "sponsored_brands",
      label: "Sponsored Brands",
      weeks: [
        {
          impressions: 40,
          clicks: 4,
          ctr_pct: 0.1,
          ad_spend: "10.00",
          cpc: "2.50",
          ad_orders: 1,
          ad_conversion_rate: 0.25,
          ad_sales: "40.00",
          acos_pct: 0.25,
          business_sales: "0.00",
          tacos_pct: null,
          tacos_available: false,
        },
      ],
    },
    {
      ad_type: "sponsored_display",
      label: "Sponsored Display",
      weeks: [
        {
          impressions: 0,
          clicks: 0,
          ctr_pct: 0,
          ad_spend: "0.00",
          cpc: "0.00",
          ad_orders: 0,
          ad_conversion_rate: 0,
          ad_sales: "0.00",
          acos_pct: 0,
          business_sales: "0.00",
          tacos_pct: null,
          tacos_available: false,
        },
      ],
    },
  ],
  ...overrides,
});

describe("buildSection2DisplayRows", () => {
  it("injects sponsored ad-type rows directly beneath an expanded row", () => {
    const rows = [
      makeRow({ id: "parent-1" }),
      makeRow({
        id: "leaf-1",
        row_kind: "leaf",
        row_label: "Leaf Row",
        parent_row_id: "parent-1",
        ad_type_breakdown: [],
      }),
    ];

    const result = buildSection2DisplayRows(rows, false, [], new Set(["parent-1"]));

    expect(result.map((row) => row.id)).toEqual([
      "parent-1",
      "parent-1__sponsored_products",
      "parent-1__sponsored_brands",
      "parent-1__sponsored_display",
      "leaf-1",
    ]);
    expect(result[1].row_kind).toBe("breakdown");
    expect(result[1].parent_row_id).toBe("parent-1");
  });
});

describe("formatSection2MetricValue", () => {
  it("renders subtype TACoS as blank", () => {
    const row = buildSection2DisplayRows([makeRow({ id: "parent-1" })], false, [], new Set(["parent-1"]))[1];
    expect(formatSection2MetricValue("tacos_pct", row, row.weeks[0])).toBe("—");
  });
});
