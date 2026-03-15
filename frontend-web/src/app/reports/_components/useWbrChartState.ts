"use client";

import { useState } from "react";

export type WbrChartMetricKey = "page_views" | "unit_sales" | "sales" | "conversion_rate";

export function useWbrChartState() {
  const [expandedMetric, setExpandedMetric] = useState<WbrChartMetricKey | null>(null);
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());

  const toggleMetric = (metricKey: WbrChartMetricKey) => {
    setExpandedMetric((current) => (current === metricKey ? null : metricKey));
    setSelectedRowIds(new Set());
  };

  const toggleRow = (rowId: string) => {
    setSelectedRowIds((current) => {
      const next = new Set(current);
      if (next.has(rowId)) {
        next.delete(rowId);
      } else {
        next.add(rowId);
      }
      return next;
    });
  };

  return {
    expandedMetric,
    selectedRowIds,
    toggleMetric,
    toggleRow,
  };
}
