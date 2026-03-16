"use client";

import { useEffect, useMemo, useState } from "react";
import type { PnlCogsMonth } from "../pnl/_lib/pnlApi";
import { formatMonth } from "../pnl/_lib/pnlDisplay";

type Props = {
  months: PnlCogsMonth[];
  loading: boolean;
  saving: boolean;
  errorMessage: string | null;
  onSave: (entries: Array<{ entry_month: string; amount: string | null }>) => Promise<void>;
};

function normalizeCurrencyInput(value: string): string {
  return value.replace(/[^0-9.-]/g, "");
}

export default function PnlCogsCard({
  months,
  loading,
  saving,
  errorMessage,
  onSave,
}: Props) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(
      Object.fromEntries(
        months.map((month) => [
          month.entry_month,
          month.amount === "0.00" ? "" : month.amount,
        ]),
      ),
    );
  }, [months]);

  const visibleMonths = useMemo(
    () => months.filter((month) => month.has_data),
    [months],
  );

  const handleSave = async () => {
    setLocalError(null);
    setSaveMessage(null);

    const entries = visibleMonths.map((month) => {
      const raw = drafts[month.entry_month]?.trim() ?? "";
      if (!raw) {
        return { entry_month: month.entry_month, amount: null };
      }
      const normalized = normalizeCurrencyInput(raw);
      if (!normalized || Number.isNaN(Number(normalized))) {
        setLocalError(`Enter a valid amount for ${formatMonth(month.entry_month)}.`);
        return null;
      }
      return { entry_month: month.entry_month, amount: normalized };
    });

    if (entries.some((entry) => entry === null)) {
      return;
    }

    try {
      await onSave(
        entries.filter((entry): entry is { entry_month: string; amount: string | null } => entry !== null),
      );
      setSaveMessage("Saved COGS month totals.");
    } catch (error) {
      setSaveMessage(null);
      setLocalError(
        error instanceof Error ? error.message : "Unable to save COGS month totals.",
      );
    }
  };

  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">COGS month totals</h2>
          <p className="mt-1 text-sm text-[#475569]">
            First usable COGS workflow: enter one total per active month. This feeds the live
            report immediately and can later expand into SKU-level entry.
          </p>
        </div>
        {loading ? <p className="text-sm text-[#64748b]">Loading COGS...</p> : null}
      </div>

      {visibleMonths.length === 0 && !loading ? (
        <p className="mt-4 text-sm text-[#64748b]">
          No active months are available for COGS entry yet.
        </p>
      ) : null}

      {visibleMonths.length > 0 ? (
        <div className="mt-4 space-y-3">
          {visibleMonths.map((month) => (
            <label
              key={month.entry_month}
              className="flex flex-col gap-2 rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="text-sm font-semibold text-[#334155]">{formatMonth(month.entry_month)}</span>
              <span className="flex items-center gap-2">
                <span className="text-sm text-[#64748b]">$</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={drafts[month.entry_month] ?? ""}
                  onChange={(event) => {
                    setDrafts((current) => ({
                      ...current,
                      [month.entry_month]: normalizeCurrencyInput(event.target.value),
                    }));
                    setLocalError(null);
                    setSaveMessage(null);
                  }}
                  placeholder="0.00"
                  className="w-full rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-right text-sm text-[#0f172a] sm:w-40"
                />
              </span>
            </label>
          ))}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving || loading}
              className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save COGS"}
            </button>
            <p className="text-sm text-[#64748b]">
              Leave a month blank to remove COGS for that month and return it to contribution framing.
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
        <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {localError ?? errorMessage}
        </p>
      ) : null}
    </div>
  );
}
