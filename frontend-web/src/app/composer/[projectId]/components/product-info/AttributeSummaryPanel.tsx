"use client";

import type { AttributeSummary } from "@/lib/composer/productInfo/inferAttributes";

interface AttributeSummaryPanelProps {
  attributes: AttributeSummary[];
  isLoading: boolean;
}

export const AttributeSummaryPanel = ({ attributes, isLoading }: AttributeSummaryPanelProps) => {
  return (
    <section className="rounded-2xl border border-dashed border-[#cbd5f5] bg-white/80 p-6 shadow-inner">
      <header className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Attribute Summary
        </p>
        <h2 className="text-lg font-semibold text-[#0f172a]">Detected Attributes</h2>
      </header>
      <p className="text-sm text-[#475569]">
        Read-only summary of attribute coverage across the SKU variants. Real counts will populate
        once SKU ingestion is wired up.
      </p>
      <ul className="mt-4 space-y-2 text-sm text-[#0f172a]">
        {isLoading ? (
          <li className="text-[#94a3b8]">Calculating attributes…</li>
        ) : attributes.length === 0 ? (
          <li className="text-[#94a3b8]">No attributes detected yet.</li>
        ) : (
          attributes.map((attribute) => (
            <li key={attribute.key} className="flex items-center justify-between rounded-xl bg-[#eef2ff] px-4 py-2">
              <span className="font-semibold">{attribute.key}</span>
              <span className="text-xs text-[#475569]">
                {attribute.filledCount}/{attribute.totalCount} SKUs
              </span>
            </li>
          ))
        )}
      </ul>
    </section>
  );
};
