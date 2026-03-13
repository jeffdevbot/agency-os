"use client";

import type { WbrSection2Row, WbrSection1Week } from "../wbr/_lib/wbrSection1Api";

type MetricKey =
  | "impressions"
  | "clicks"
  | "ctr_pct"
  | "ad_spend"
  | "cpc"
  | "ad_orders"
  | "ad_conversion_rate"
  | "ad_sales"
  | "acos_pct";

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

export const buildSection2DisplayRows = (
  rows: WbrSection2Row[],
  hideEmptyRows: boolean,
  referenceRowOrder: string[]
): WbrSection2Row[] => {
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

  const ordered: WbrSection2Row[] = [];
  roots.forEach((root) => {
    ordered.push(root);
    const children = childrenByParent.get(root.id) ?? [];
    children.forEach((child) => ordered.push(child));
  });

  return ordered;
};

export const buildSection2TotalValues = (
  rows: WbrSection2Row[],
  weeks: WbrSection1Week[],
  metricKey: MetricKey,
  hideEmptyRows: boolean
): string[] => {
  const topLevelRows = (hideEmptyRows ? rows.filter(getRowHasActivity) : rows).filter((row) => !row.parent_row_id);

  return weeks.map((_, weekIndex) => {
    if (metricKey === "ad_spend" || metricKey === "ad_sales" || metricKey === "cpc") {
      if (metricKey === "cpc") {
        const clicks = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.clicks || 0), 0);
        const spend = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_spend || 0), 0);
        const cpc = clicks === 0 ? 0 : spend / clicks;
        return new Intl.NumberFormat("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(cpc);
      }

      const total = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.[metricKey] || 0), 0);
      return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(total);
    }

    if (metricKey === "ctr_pct") {
      const impressions = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.impressions || 0), 0);
      const clicks = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.clicks || 0), 0);
      const rate = impressions === 0 ? 0 : clicks / impressions;
      return `${(rate * 100).toFixed(1)}%`;
    }

    if (metricKey === "ad_conversion_rate") {
      const clicks = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.clicks || 0), 0);
      const orders = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_orders || 0), 0);
      const rate = clicks === 0 ? 0 : orders / clicks;
      return `${(rate * 100).toFixed(1)}%`;
    }

    if (metricKey === "acos_pct") {
      const spend = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_spend || 0), 0);
      const sales = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.ad_sales || 0), 0);
      const rate = sales === 0 ? 0 : spend / sales;
      return `${(rate * 100).toFixed(1)}%`;
    }

    const total = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.[metricKey] || 0), 0);
    return new Intl.NumberFormat("en-US").format(total);
  });
};

export const hasAnySection2Activity = (rows: WbrSection2Row[]): boolean => rows.some(getRowHasActivity);
