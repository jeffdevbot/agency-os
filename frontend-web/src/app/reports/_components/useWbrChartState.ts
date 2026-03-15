"use client";

import { useState } from "react";

export function useWbrChartState<MetricKey extends string>() {
  const [expandedMetric, setExpandedMetric] = useState<MetricKey | null>(null);
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());
  const [showTotal, setShowTotal] = useState(true);

  const toggleMetric = (metricKey: MetricKey) => {
    setExpandedMetric((current) => (current === metricKey ? null : metricKey));
    setSelectedRowIds(new Set());
    setShowTotal(true);
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

  const toggleTotal = () => {
    setShowTotal((current) => !current);
  };

  return {
    expandedMetric,
    selectedRowIds,
    showTotal,
    toggleMetric,
    toggleRow,
    toggleTotal,
  };
}
