"use client";

import { useState } from "react";
import type { RemovedKeywordEntry } from "@agency/lib/composer/types";

interface RemovedKeywordsListProps {
  removed: RemovedKeywordEntry[];
  onRestore: (keyword: string) => void;
}

// Reason badge colors mapping
const REASON_COLORS: Record<string, string> = {
  duplicate: "bg-gray-100 text-gray-700",
  color: "bg-blue-100 text-blue-700",
  size: "bg-purple-100 text-purple-700",
  brand: "bg-orange-100 text-orange-700",
  competitor: "bg-red-100 text-red-700",
  stopword: "bg-yellow-100 text-yellow-700",
  manual: "bg-pink-100 text-pink-700",
};

const getReasonColor = (reason: string): string => {
  return REASON_COLORS[reason] || "bg-gray-100 text-gray-700";
};

export const RemovedKeywordsList = ({ removed, onRestore }: RemovedKeywordsListProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedReasons, setExpandedReasons] = useState<Set<string>>(new Set());

  if (!removed.length) {
    return null;
  }

  // Group keywords by reason
  const grouped = removed.reduce((acc, entry) => {
    const key = entry.reason;
    if (!acc[key]) acc[key] = [];
    acc[key].push(entry);
    return acc;
  }, {} as Record<string, RemovedKeywordEntry[]>);

  const toggleReason = (reason: string) => {
    setExpandedReasons((prev) => {
      const next = new Set(prev);
      if (next.has(reason)) {
        next.delete(reason);
      } else {
        next.add(reason);
      }
      return next;
    });
  };

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white overflow-hidden">
      {/* Header - Always Visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-[#fef2f2] hover:bg-[#fee2e2] transition-colors text-left"
      >
        <div className="flex-1">
          <h4 className="font-semibold text-[#0f172a]">
            Removed Keywords ({removed.length})
          </h4>
          <p className="text-xs text-[#64748b] mt-1">
            {isExpanded
              ? "Click to collapse list"
              : "Keywords filtered out during cleanup"}
          </p>
        </div>
        <div className="ml-4 text-[#64748b] text-lg">
          {isExpanded ? "▲" : "▼"}
        </div>
      </button>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="border-t border-[#e2e8f0]">
          <div className="max-h-[400px] overflow-y-auto">
            <div className="divide-y divide-[#e2e8f0]">
              {Object.entries(grouped)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([reason, entries]) => {
                  const isReasonExpanded = expandedReasons.has(reason);
                  const count = entries.length;

                  return (
                    <div key={reason}>
                      {/* Reason Group Header */}
                      <button
                        onClick={() => toggleReason(reason)}
                        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[#f8fafc] transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-[#64748b]">
                            {isReasonExpanded ? "▼" : "▶"}
                          </span>
                          <span className="font-medium text-[#0f172a] capitalize">
                            {reason} ({count})
                          </span>
                        </div>
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${getReasonColor(
                            reason
                          )}`}
                        >
                          {reason}
                        </span>
                      </button>

                      {/* Reason Group Content */}
                      {isReasonExpanded && (
                        <div className="bg-[#f8fafc] px-4 py-3">
                          <div className="space-y-2">
                            {entries.map((entry, index) => (
                              <div
                                key={`${entry.term}-${index}`}
                                className="flex items-center justify-between rounded-lg bg-white px-3 py-2 shadow-sm border border-[#e2e8f0]"
                              >
                                <span className="text-sm text-[#475569]">
                                  {entry.term}
                                </span>
                                <button
                                  className="text-xs font-semibold text-[#0a6fd6] hover:underline"
                                  onClick={() => onRestore(entry.term)}
                                >
                                  Restore
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Footer with Total Count */}
          <div className="border-t border-[#e2e8f0] bg-[#fef2f2] px-4 py-2">
            <p className="text-xs text-[#64748b] text-center">
              Showing all {removed.length} removed {removed.length === 1 ? "keyword" : "keywords"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
