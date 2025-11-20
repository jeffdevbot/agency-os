"use client";

interface CleanedKeywordsListProps {
  keywords: string[];
  onRemove: (keyword: string) => void;
}

export const CleanedKeywordsList = ({ keywords, onRemove }: CleanedKeywordsListProps) => {
  if (!keywords.length) {
    return <p className="text-sm text-[#94a3b8]">No cleaned keywords yet.</p>;
  }
  return (
    <div className="space-y-2">
      {keywords.map((keyword) => (
        <div
          key={keyword}
          className="flex items-center justify-between rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#0f172a]"
        >
          <span>{keyword}</span>
          <button
            className="text-xs font-semibold text-[#b91c1c] hover:underline"
            onClick={() => onRemove(keyword)}
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
};
