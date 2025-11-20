"use client";

import type { RemovedKeywordEntry } from "@agency/lib/composer/types";

interface RemovedKeywordsListProps {
  removed: RemovedKeywordEntry[];
  onRestore: (keyword: string) => void;
}

export const RemovedKeywordsList = ({ removed, onRestore }: RemovedKeywordsListProps) => {
  if (!removed.length) {
    return <p className="text-sm text-[#94a3b8]">No removed keywords.</p>;
  }
  return (
    <div className="space-y-2">
      {removed.map((entry) => (
        <div
          key={`${entry.term}-${entry.reason}`}
          className="flex items-center justify-between rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#0f172a]"
        >
          <div className="flex items-center gap-2">
            <span>{entry.term}</span>
            <span className="rounded-full bg-[#eef2ff] px-2 py-0.5 text-xs text-[#4338ca]">
              {entry.reason}
            </span>
          </div>
          <button
            className="text-xs font-semibold text-[#0a6fd6] hover:underline"
            onClick={() => onRestore(entry.term)}
          >
            Restore
          </button>
        </div>
      ))}
    </div>
  );
};
