"use client";

import { useState } from "react";

interface CleanedKeywordsListProps {
  keywords: string[];
  onRemove: (keyword: string) => void;
}

export const CleanedKeywordsList = ({ keywords, onRemove }: CleanedKeywordsListProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!keywords.length) {
    return null;
  }

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white overflow-hidden">
      {/* Header - Always Visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-[#f8fafc] hover:bg-[#f1f5f9] transition-colors text-left"
      >
        <div className="flex-1">
          <h4 className="font-semibold text-[#0f172a]">
            Cleaned Keywords ({keywords.length})
          </h4>
          <p className="text-xs text-[#64748b] mt-1">
            {isExpanded
              ? "Click to collapse list"
              : "Click to expand and review keywords"}
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
            <div className="p-3 space-y-2">
              {keywords.map((keyword, index) => (
                <div
                  key={`${keyword}-${index}`}
                  className="flex items-center justify-between rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#0f172a] hover:border-[#cbd5e1] transition-colors group"
                >
                  <span>{keyword}</span>
                  <button
                    className="text-xs font-semibold text-[#b91c1c] hover:underline opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => onRemove(keyword)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Footer with Total Count */}
          <div className="border-t border-[#e2e8f0] bg-[#f8fafc] px-4 py-2">
            <p className="text-xs text-[#64748b] text-center">
              Showing all {keywords.length} cleaned {keywords.length === 1 ? "keyword" : "keywords"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
