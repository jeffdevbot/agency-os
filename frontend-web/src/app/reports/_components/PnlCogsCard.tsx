"use client";

import { useEffect, useMemo, useState } from "react";
import type { PnlSkuCogs } from "../pnl/_lib/pnlApi";
import {
  downloadPnlCogsCsv,
  parsePnlCogsCsv,
} from "../pnl/_lib/pnlCogsCsv";
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

const COLLAPSED_ROW_COUNT = 8;

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
  const [showAllRows, setShowAllRows] = useState(false);
  const [selectedCsvFile, setSelectedCsvFile] = useState<File | null>(null);
  const [importingCsv, setImportingCsv] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

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

  useEffect(() => {
    if (skus.length <= COLLAPSED_ROW_COUNT) {
      setShowAllRows(false);
    }
  }, [skus.length]);

  const allSkus = useMemo(() => skus, [skus]);
  const visibleSkus = useMemo(
    () => (showAllRows ? allSkus : allSkus.slice(0, COLLAPSED_ROW_COUNT)),
    [allSkus, showAllRows],
  );

  const handleSave = async () => {
    setLocalError(null);
    setSaveMessage(null);

    const entries = allSkus.map((row) => {
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

  const handleExportCsv = () => {
    setLocalError(null);
    setSaveMessage(null);

    if (allSkus.length === 0) {
      setLocalError("No sold SKUs are available to export for this profile yet.");
      return;
    }

    try {
      setExportingCsv(true);
      downloadPnlCogsCsv("amazon-pnl-sku-cogs.csv", allSkus);
      setSaveMessage("Downloaded SKU COGS CSV.");
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Unable to export SKU COGS CSV.",
      );
    } finally {
      setExportingCsv(false);
    }
  };

  const handleImportCsv = async () => {
    if (!selectedCsvFile) {
      setLocalError("Choose a CSV file to import.");
      return;
    }

    setImportingCsv(true);
    setLocalError(null);
    setSaveMessage(null);

    try {
      const importedEntries = await parsePnlCogsCsv(selectedCsvFile);
      const allowedSkus = new Set(allSkus.map((row) => row.sku));
      const unknownSku = importedEntries.find((entry) => !allowedSkus.has(entry.sku));
      if (unknownSku) {
        throw new Error(
          `COGS CSV references ${unknownSku.sku}, which is not in the current profile SKU list.`,
        );
      }
      const importedSkuSet = new Set(importedEntries.map((entry) => entry.sku));
      const missingSku = allSkus.find((row) => !importedSkuSet.has(row.sku));
      if (missingSku) {
        throw new Error(
          `COGS CSV is missing ${missingSku.sku}. Re-upload the full exported SKU list to rewrite COGS safely.`,
        );
      }

      const importedBySku = new Map(importedEntries.map((entry) => [entry.sku, entry]));
      const rewriteEntries = allSkus.map((row) => {
        const imported = importedBySku.get(row.sku);
        if (!imported) {
          throw new Error(
            `COGS CSV is missing ${row.sku}. Re-upload the full exported SKU list to rewrite COGS safely.`,
          );
        }
        return imported;
      });

      await onSave(rewriteEntries);
      setSelectedCsvFile(null);
      setSaveMessage(
        `Imported SKU COGS CSV and rewrote ${rewriteEntries.length} SKU${rewriteEntries.length === 1 ? "" : "s"}.`,
      );
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Unable to import SKU COGS CSV.",
      );
    } finally {
      setImportingCsv(false);
    }
  };

  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">COGS by SKU</h2>
          <p className="mt-1 text-sm text-[#475569]">
            Enter one current unit cost per sold SKU across all active imported months for this
            profile. Monthly COGS is calculated automatically from sold quantities in each report
            window.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {loading ? <p className="text-sm text-[#64748b]">Loading COGS...</p> : null}
          <button
            type="button"
            onClick={handleExportCsv}
            disabled={loading || saving || importingCsv || exportingCsv || allSkus.length === 0}
            className="rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] transition hover:border-[#94a3b8] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exportingCsv ? "Exporting..." : "Export CSV"}
          </button>
        </div>
      </div>

      {allSkus.length === 0 && !loading && !errorMessage ? (
        <p className="mt-4 text-sm text-[#64748b]">
          No sold SKUs were found across the active imported months for this profile.
        </p>
      ) : null}

      {allSkus.length > 0 ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px_auto] md:items-end">
              <label className="text-sm">
                <span className="mb-1 block font-semibold text-[#0f172a]">Import CSV</span>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(event) => setSelectedCsvFile(event.target.files?.[0] ?? null)}
                  className="block w-full rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-sm text-[#0f172a] file:mr-4 file:rounded-lg file:border-0 file:bg-[#0a6fd6] file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
                />
              </label>
              <div className="text-xs text-[#64748b] md:pb-2">
                Re-upload the full exported SKU list to rewrite COGS. Leave `unit_cost` blank to clear it.
                {selectedCsvFile ? <p className="mt-1">Selected: {selectedCsvFile.name}</p> : null}
              </div>
              <button
                type="button"
                onClick={() => void handleImportCsv()}
                disabled={!selectedCsvFile || loading || saving || importingCsv || exportingCsv}
                className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {importingCsv ? "Importing..." : "Import CSV"}
              </button>
            </div>
          </div>

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

          {allSkus.length > COLLAPSED_ROW_COUNT ? (
            <button
              type="button"
              onClick={() => setShowAllRows((current) => !current)}
              className="rounded-xl border border-[#dbe4f0] bg-white px-4 py-2 text-sm font-semibold text-[#475569] transition hover:border-[#94a3b8] hover:text-[#0f172a]"
            >
              {showAllRows
                ? `Show fewer SKUs`
                : `See more (${allSkus.length - COLLAPSED_ROW_COUNT} more)`}
            </button>
          ) : null}

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
