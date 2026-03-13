"use client";

import type { WbrSection1Row, WbrSection1Week } from "../wbr/_lib/wbrSection1Api";

type MetricKey = "page_views" | "unit_sales" | "sales" | "conversion_rate";

const getRowPageViewTotal = (row: WbrSection1Row): number =>
  row.weeks.reduce((sum, week) => sum + Number(week.page_views || 0), 0);

const getRowHasActivity = (row: WbrSection1Row): boolean =>
  row.weeks.some(
    (week) => week.page_views > 0 || week.unit_sales > 0 || Number(week.sales || 0) > 0
  );

const compareRowsForDisplay = (left: WbrSection1Row, right: WbrSection1Row): number => {
  const pageViewDelta = getRowPageViewTotal(right) - getRowPageViewTotal(left);
  if (pageViewDelta !== 0) return pageViewDelta;

  const sortOrderDelta = Number(left.sort_order || 0) - Number(right.sort_order || 0);
  if (sortOrderDelta !== 0) return sortOrderDelta;

  return left.row_label.localeCompare(right.row_label);
};

export const buildDisplayRows = (rows: WbrSection1Row[], hideEmptyRows: boolean): WbrSection1Row[] => {
  const rowsToDisplay = hideEmptyRows ? rows.filter(getRowHasActivity) : rows;
  const childrenByParent = new Map<string, WbrSection1Row[]>();
  const roots: WbrSection1Row[] = [];

  rowsToDisplay.forEach((row) => {
    if (row.parent_row_id) {
      const current = childrenByParent.get(row.parent_row_id) ?? [];
      current.push(row);
      childrenByParent.set(row.parent_row_id, current);
      return;
    }
    roots.push(row);
  });

  roots.sort(compareRowsForDisplay);
  childrenByParent.forEach((children) => children.sort(compareRowsForDisplay));

  const ordered: WbrSection1Row[] = [];
  roots.forEach((root) => {
    ordered.push(root);
    const children = childrenByParent.get(root.id) ?? [];
    children.forEach((child) => ordered.push(child));
  });

  return ordered;
};

export const buildTotalValues = (
  rows: WbrSection1Row[],
  weeks: WbrSection1Week[],
  metricKey: MetricKey,
  hideEmptyRows: boolean
): string[] => {
  const topLevelRows = (hideEmptyRows ? rows.filter(getRowHasActivity) : rows).filter((row) => !row.parent_row_id);

  return weeks.map((_, weekIndex) => {
    if (metricKey === "sales") {
      const total = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.sales || 0), 0);
      return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(total);
    }

    if (metricKey === "conversion_rate") {
      const pageViews = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.page_views || 0), 0);
      const unitSales = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.unit_sales || 0), 0);
      const rate = pageViews === 0 ? 0 : unitSales / pageViews;
      return `${(rate * 100).toFixed(1)}%`;
    }

    const total = topLevelRows.reduce((sum, row) => sum + Number(row.weeks[weekIndex]?.[metricKey] || 0), 0);
    return new Intl.NumberFormat("en-US").format(total);
  });
};

export const hasAnyActivity = (rows: WbrSection1Row[]): boolean => rows.some(getRowHasActivity);
