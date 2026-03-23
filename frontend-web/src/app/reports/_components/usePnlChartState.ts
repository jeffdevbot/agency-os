"use client";

import { useCallback, useState } from "react";

export function usePnlChartState() {
  const [selectedRowKeys, setSelectedRowKeys] = useState<Set<string>>(new Set());
  const [showTotal, setShowTotal] = useState(false);

  const toggleRow = useCallback((key: string) => {
    setSelectedRowKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const toggleTotal = useCallback(() => {
    setShowTotal((current) => !current);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedRowKeys(new Set());
    setShowTotal(false);
  }, []);

  return {
    selectedRowKeys,
    showTotal,
    toggleRow,
    toggleTotal,
    clearSelection,
  };
}
