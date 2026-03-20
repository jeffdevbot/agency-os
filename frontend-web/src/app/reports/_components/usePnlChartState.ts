"use client";

import { useState } from "react";

export function usePnlChartState() {
  const [selectedRowKeys, setSelectedRowKeys] = useState<Set<string>>(new Set());
  const [showTotal, setShowTotal] = useState(false);

  const toggleRow = (key: string) => {
    setSelectedRowKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const toggleTotal = () => {
    setShowTotal((current) => !current);
  };

  return {
    selectedRowKeys,
    showTotal,
    toggleRow,
    toggleTotal,
  };
}
