"use client";

import { useEffect, useMemo, useState } from "react";
import type { PnlSkuCogs } from "../pnl/_lib/pnlApi";
import { formatMonth } from "../pnl/_lib/pnlDisplay";

type Props = {
  skus: PnlSkuCogs[];
  loading: boolean;
  saving: boolean;
  errorMessage: string | null;
  onRetry: () => void;
  onSave: (entries: Array<{ sku: string; unit_cost: string | null }>) => Promise<void>;
};

function normalizeCurrencyInput(value: string): string {
  return value.replace(/[^0-9.-]/g, "");
}

export default function PnlCogsCard({
  skus,
  loading,
  saving,
  errorMessage,
  onRetry,
  onSave,
}: Props) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(
      Object.fromEntries(
        skus.map((row) => [
          row.sku,
          row.unit_cost ?? "",
        ]),
      ),
    );
  }, [skus]);

  const visibleSkus = useMemo(() => skus, [skus]);

  const handleSave = async () => {
    setLocalError(null);
    setSaveMessage(null);

    const entries = visibleSkus.map((row) => {
      const raw = drafts[row.sku]?.trim() ?? "";
      if (!raw) {
        return { sku: row.sku, unit_cost: null };
      }
      const normalized = normalizeCurrencyInput(raw);
      if (!normalized || Number.isNaN(Number(normalized))) {
        setLocalError(`Enter a valid unit cost for ${row.sku}.`);
        return null;
      }
      return { sku: row.sku, unit_cost: normalized };
    });

    if (entries.some((entry) => entry === null)) {
      return;
    }

    try {
      await onSave(
        entries.filter((entry): entry is { sku: string; unit_cost: string | null } => entry !== null),
      );
      setSaveMessage("Saved SKU COGS.");
    } catch (error) {
      setSaveMessage(null);
      setLocalError(
        error instanceof Error ? error.message : "Unable to save SKU COGS.",
      );
    }
  };

  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">COGS by SKU</h2>
          <p className="mt-1 text-sm text-[#475569]">
            Enter one current unit cost per sold SKU. Monthly COGS is calculated automatically from
            the sold quantity in the visible report range.
          </p>
        </div>
        {loading ? <p className="text-sm text-[#64748b]">Loading COGS...</p> : null}
      </div>

      {visibleSkus.length === 0 && !loading && !errorMessage ? (
        <p className="mt-4 text-sm text-[#64748b]">
          No sold SKUs were found in the visible report range.
        </p>
      ) : null}

      {visibleSkus.length > 0 ? (
        <div className="mt-4 space-y-3">
          {visibleSkus.map((row) => (
            <div
              key={row.sku}
              className={`rounded-2xl border px-4 py-3 ${
                row.missing_cost
                  ? "border-[#fbbf24]/40 bg-[#fff7d6]"
                  : "border-[#dbe4f0] bg-[#f8fafc]"
              }`}
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-[#0f172a]">{row.sku}</span>
                    {row.missing_cost ? (
                      <span className="rounded-full bg-[#fbbf24]/20 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#92400e]">
                        Missing cost
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm text-[#475569]">
                    Net units in range: <span className="font-semibold text-[#0f172a]">{row.total_units}</span>
                  </p>
                  <p className="mt-1 text-xs text-[#64748b]">
                    {Object.entries(row.months)
                      .sort(([left], [right]) => left.localeCompare(right))
                      .map(([month, units]) => `${formatMonth(month)}: ${units}`)
                      .join(" • ")}
                  </p>
                </div>
                <label className="flex items-center gap-2 lg:ml-4">
                  <span className="text-sm text-[#64748b]">$</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={drafts[row.sku] ?? ""}
                    onChange={(event) => {
                      setDrafts((current) => ({
                        ...current,
                        [row.sku]: normalizeCurrencyInput(event.target.value),
                      }));
                      setLocalError(null);
                      setSaveMessage(null);
                    }}
                    placeholder="0.00"
                    className="w-full rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-right text-sm text-[#0f172a] sm:w-40"
                  />
                </label>
              </div>
            </div>
          ))}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving || loading}
              className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save SKU COGS"}
            </button>
            <p className="text-sm text-[#64748b]">
              Leave a SKU blank to remove its stored unit cost.
            </p>
          </div>
        </div>
      ) : null}

      {saveMessage ? (
        <p className="mt-4 rounded-xl border border-[#86efac]/40 bg-[#dcfce7] px-4 py-3 text-sm text-[#166534]">
          {saveMessage}
        </p>
      ) : null}
      {localError || errorMessage ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          <p>{localError ?? errorMessage}</p>
          {errorMessage && !localError ? (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-full border border-[#fca5a5] bg-white px-3 py-1 text-xs font-semibold text-[#991b1b] transition hover:border-[#ef4444]"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
