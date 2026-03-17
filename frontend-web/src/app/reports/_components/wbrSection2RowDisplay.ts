"use client";

import type { WbrSection2Row, WbrSection1Week, WbrSection2RowWeek } from "../wbr/_lib/wbrSection1Api";

export type WbrSection2MetricKey =
  | "impressions"
  | "clicks"
  | "ctr_pct"
  | "ad_spend"
  | "cpc"
  | "ad_orders"
  | "ad_conversion_rate"
  | "ad_sales"
  | "acos_pct"
  | "tacos_pct";

export type WbrSection2DisplayRow = WbrSection2Row & {
  breakdown_parent_id?: string;
};

const getRowHasActivity = (row: WbrSection2Row): boolean =>
  row.weeks.some(
    (week) =>
      week.impressions > 0 ||
      week.clicks > 0 ||
      Number(week.ad_spend || 0) > 0 ||
      week.ad_orders > 0 ||
      Number(week.ad_sales || 0) > 0
  );

const compareRowsByReference = (
  left: WbrSection2Row,
  right: WbrSection2Row,
  rowOrderMap: Map<string, number>
): number => {
  const leftIndex = rowOrderMap.get(left.id);
  const rightIndex = rowOrderMap.get(right.id);
  if (leftIndex !== undefined || rightIndex !== undefined) {
    if (leftIndex === undefined) return 1;
    if (rightIndex === undefined) return -1;
    if (leftIndex !== rightIndex) return leftIndex - rightIndex;
  }

  const sortOrderDelta = Number(left.sort_order || 0) - Number(right.sort_order || 0);
  if (sortOrderDelta !== 0) return sortOrderDelta;

  return left.row_label.localeCompare(right.row_label);
};

export const isSection2BreakdownRow = (row: WbrSection2DisplayRow): boolean => row.row_kind === "breakdown";

export const isSection2ExpandableRow = (row: WbrSection2Row): boolean =>
  (row.row_kind === "parent" || row.row_kind === "leaf") && row.ad_type_breakdown.length > 0;

export const formatSection2MetricValue = (
  metricKey: WbrSection2MetricKey,
  row: WbrSection2DisplayRow,
  values: WbrSection2RowWeek
): string => {
  if (metricKey === "tacos_pct" && row.row_kind === "breakdown" && values.tacos_available === false) {
    return "—";
  }

  if (metricKey === "ad_spend" || metricKey === "ad_sales" || metricKey === "cpc") {
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(values[metricKey] || 0));
  }

  if (metricKey === "ctr_pct" || metricKey === "ad_conversion_rate" || metricKey === "acos_pct" || metricKey === "tacos_pct") {
    return `${((values[metricKey] ?? 0) * 100).toFixed(1)}%`;
  }

  return new Intl.NumberFormat("en-US").format(values[metricKey]);
};

export const buildSection2DisplayRows = (
  rows: WbrSection2Row[],
  hideEmptyRows: boolean,
  referenceRowOrder: string[],
  expandedRowIds: Set<string> = new Set()
): WbrSection2DisplayRow[] => {
  const rowsToDisplay = hideEmptyRows ? rows.filter(getRowHasActivity) : rows;
  const rowOrderMap = new Map(referenceRowOrder.map((rowId, index) => [rowId, index]));
  const childrenByParent = new Map<string, WbrSection2Row[]>();
  const roots: WbrSection2Row[] = [];

  rowsToDisplay.forEach((row) => {
    if (row.parent_row_id) {
      const current = childrenByParent.get(row.parent_row_id) ?? [];
      current.push(row);
      childrenByParent.set(row.parent_row_id, current);
      return;
    }
    roots.push(row);
  });

  roots.sort((left, right) => compareRowsByReference(left, right, rowOrderMap));
  childrenByParent.forEach((children) =>
    children.sort((left, right) => compareRowsByReference(left, right, rowOrderMap))
  );

  const ordered: WbrSection2DisplayRow[] = [];
  roots.forEach((root) => {
    ordered.push(root);
    if (expandedRowIds.has(root.id) && isSection2ExpandableRow(root)) {
      root.ad_type_breakdown.forEach((breakdown) => {
        ordered.push({
          id: `${root.id}__${breakdown.ad_type}`,
          row_label: breakdown.label,
          row_kind: "breakdown",
          parent_row_id: root.id,
          sort_order: root.sort_order,
          weeks: breakdown.weeks,
          ad_type_breakdown: [],
          breakdown_parent_id: root.id,
        });
      });
    }
    const children = childrenByParent.get(root.id) ?? [];
    children.forEach((child) => {
      ordered.push(child);
      if (expandedRowIds.has(child.id) && isSection2ExpandableRow(child)) {
        child.ad_type_breakdown.forEach((breakdown) => {
          ordered.push({
            id: `${child.id}__${breakdown.ad_type}`,
            row_label: breakdown.label,
            row_kind: "breakdown",
            parent_row_id: child.id,
            sort_order: child.sort_order,
            weeks: breakdown.weeks,
            ad_type_breakdown: [],
            breakdown_parent_id: child.id,
          });
        });
      }
    });
  });

  return ordered;
};

export const getSection2TotalValue = (
  rows: WbrSection2Row[],
  weekIndex: number,
  metricKey: WbrSection2MetricKey,
  hideEmptyRows: boolean
): number => {
  const topLevelRows = (hideEmptyRows ? rows.filter(getRowHasActivity) : rows).filter((row) => !row.parent_row_id);

  if (metricKey === "cpc") {
    const clicks = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.clicks || 0), 0);
    const spend = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_spend || 0), 0);
    return clicks === 0 ? 0 : spend / clicks;
  }

  if (metricKey === "ctr_pct") {
    const impressions = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.impressions || 0), 0);
    const clicks = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.clicks || 0), 0);
    return impressions === 0 ? 0 : clicks / impressions;
  }

  if (metricKey === "ad_conversion_rate") {
    const clicks = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.clicks || 0), 0);
    const orders = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_orders || 0), 0);
    return clicks === 0 ? 0 : orders / clicks;
  }

  if (metricKey === "acos_pct") {
    const spend = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_spend || 0), 0);
    const sales = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_sales || 0), 0);
    return sales === 0 ? 0 : spend / sales;
  }

  if (metricKey === "tacos_pct") {
    const spend = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_spend || 0), 0);
    const businessSales = topLevelRows.reduce(
      (sum, row) => sum + Number(row.weeks[weekIndex]?.business_sales || 0),
      0
    );
    return businessSales === 0 ? 0 : spend / businessSales;
  }

  return topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.[metricKey] || 0), 0);
};

export const buildSection2TotalValues = (
  rows: WbrSection2Row[],
  weeks: WbrSection1Week[],
  metricKey: WbrSection2MetricKey,
  hideEmptyRows: boolean
): string[] => {
  return weeks.map((_, weekIndex) => {
    const total = getSection2TotalValue(rows, weekIndex, metricKey, hideEmptyRows);

    if (metricKey === "ad_spend" || metricKey === "ad_sales" || metricKey === "cpc") {
      return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(total);
    }

    if (metricKey === "ctr_pct") {
      return `${(total * 100).toFixed(1)}%`;
    }

    if (metricKey === "ad_conversion_rate") {
      return `${(total * 100).toFixed(1)}%`;
    }

    if (metricKey === "acos_pct") {
      return `${(total * 100).toFixed(1)}%`;
    }

    if (metricKey === "tacos_pct") {
      return `${(total * 100).toFixed(1)}%`;
    }

    return new Intl.NumberFormat("en-US").format(total);
  });
};

export const hasAnySection2Activity = (rows: WbrSection2Row[]): boolean => rows.some(getRowHasActivity);
