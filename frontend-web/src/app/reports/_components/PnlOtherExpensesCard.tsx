"use client";

import { useEffect, useMemo, useState } from "react";
import type { PnlOtherExpenseMonth, PnlOtherExpenseType } from "../pnl/_lib/pnlApi";
import {
  downloadPnlOtherExpensesCsv,
  parsePnlOtherExpensesCsv,
} from "../pnl/_lib/pnlOtherExpensesCsv";
import { formatMonth } from "../pnl/_lib/pnlDisplay";

type Props = {
  expenseTypes: PnlOtherExpenseType[];
  months: PnlOtherExpenseMonth[];
  loading: boolean;
  saving: boolean;
  errorMessage: string | null;
  onRetry: () => void;
  onSave: (payload: {
    expense_types: Array<{ key: string; enabled: boolean }>;
    months: Array<{ entry_month: string; values: Record<string, string | null> }>;
  }) => Promise<void>;
};

function normalizeCurrencyInput(value: string): string {
  return value.replace(/[^0-9.-]/g, "");
}

export default function PnlOtherExpensesCard({
  expenseTypes,
  months,
  loading,
  saving,
  errorMessage,
  onRetry,
  onSave,
}: Props) {
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>({});
  const [enabledByKey, setEnabledByKey] = useState<Record<string, boolean>>({});
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [selectedCsvFile, setSelectedCsvFile] = useState<File | null>(null);
  const [importingCsv, setImportingCsv] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  useEffect(() => {
    setDrafts(
      Object.fromEntries(
        months.map((month) => [
          month.entry_month,
          Object.fromEntries(
            expenseTypes.map((expenseType) => [
              expenseType.key,
              month.values[expenseType.key] ?? "",
            ]),
          ),
        ]),
      ),
    );
  }, [expenseTypes, months]);

  useEffect(() => {
    setEnabledByKey(
      Object.fromEntries(expenseTypes.map((expenseType) => [expenseType.key, expenseType.enabled])),
    );
  }, [expenseTypes]);

  const orderedMonths = useMemo(() => months, [months]);

  const buildPayload = () => {
    const normalizedMonths = orderedMonths.map((month) => {
      const draftValues = drafts[month.entry_month] ?? {};
      const values = Object.fromEntries(
        expenseTypes.map((expenseType) => {
          const raw = draftValues[expenseType.key]?.trim() ?? "";
          if (!raw) {
            return [expenseType.key, null];
          }
          const normalized = normalizeCurrencyInput(raw);
          if (!normalized || Number.isNaN(Number(normalized))) {
            throw new Error(
              `Enter a valid amount for ${expenseType.label} in ${formatMonth(month.entry_month)}.`,
            );
          }
          if (Number(normalized) < 0) {
            throw new Error(
              `${expenseType.label} cannot be negative in ${formatMonth(month.entry_month)}.`,
            );
          }
          return [expenseType.key, normalized];
        }),
      );

      return {
        entry_month: month.entry_month,
        values,
      };
    });

    return {
      expense_types: expenseTypes.map((expenseType) => ({
        key: expenseType.key,
        enabled: enabledByKey[expenseType.key] ?? false,
      })),
      months: normalizedMonths,
    };
  };

  const handleSave = async () => {
    setLocalError(null);
    setSaveMessage(null);

    try {
      await onSave(buildPayload());
      setSaveMessage("Saved other expenses.");
    } catch (error) {
      setSaveMessage(null);
      setLocalError(
        error instanceof Error ? error.message : "Unable to save other expenses.",
      );
    }
  };

  const handleExportCsv = () => {
    setLocalError(null);
    setSaveMessage(null);

    if (orderedMonths.length === 0 || expenseTypes.length === 0) {
      setLocalError("No visible months are available to export for other expenses.");
      return;
    }

    try {
      setExportingCsv(true);
      downloadPnlOtherExpensesCsv(
        "amazon-pnl-other-expenses.csv",
        orderedMonths,
        expenseTypes,
      );
      setSaveMessage("Downloaded other expenses CSV.");
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Unable to export other expenses CSV.",
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
      const importedMonths = await parsePnlOtherExpensesCsv(selectedCsvFile, expenseTypes);
      const allowedMonths = new Set(orderedMonths.map((month) => month.entry_month));
      const unknownMonth = importedMonths.find((month) => !allowedMonths.has(month.entry_month));
      if (unknownMonth) {
        throw new Error(
          `Other expenses CSV references ${unknownMonth.entry_month}, which is not in the current visible month list.`,
        );
      }
      const importedMonthSet = new Set(importedMonths.map((month) => month.entry_month));
      const missingMonth = orderedMonths.find((month) => !importedMonthSet.has(month.entry_month));
      if (missingMonth) {
        throw new Error(
          `Other expenses CSV is missing ${missingMonth.entry_month}. Re-upload the full exported month list to rewrite safely.`,
        );
      }

      const importedByMonth = new Map(
        importedMonths.map((month) => [month.entry_month, month.values]),
      );
      const rewrittenMonths = orderedMonths.map((month) => ({
        entry_month: month.entry_month,
        values: importedByMonth.get(month.entry_month) ?? {},
      }));

      await onSave({
        expense_types: expenseTypes.map((expenseType) => ({
          key: expenseType.key,
          enabled: enabledByKey[expenseType.key] ?? false,
        })),
        months: rewrittenMonths,
      });
      setSelectedCsvFile(null);
      setSaveMessage(
        `Imported other expenses CSV and rewrote ${rewrittenMonths.length} month${rewrittenMonths.length === 1 ? "" : "s"}.`,
      );
    } catch (error) {
      setLocalError(
        error instanceof Error ? error.message : "Unable to import other expenses CSV.",
      );
    } finally {
      setImportingCsv(false);
    }
  };

  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">Other expenses</h2>
          <p className="mt-1 text-sm text-[#475569]">
            Add manual monthly expenses that do not come from the Amazon transaction upload, then
            choose whether each row should appear in the report.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {loading ? <p className="text-sm text-[#64748b]">Loading other expenses...</p> : null}
          <button
            type="button"
            onClick={handleExportCsv}
            disabled={loading || saving || importingCsv || exportingCsv || orderedMonths.length === 0}
            className="rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] transition hover:border-[#94a3b8] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exportingCsv ? "Exporting..." : "Export CSV"}
          </button>
        </div>
      </div>

      {errorMessage ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          <p>{errorMessage}</p>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-full border border-[#fca5a5] bg-white px-3 py-1 text-xs font-semibold text-[#991b1b] transition hover:border-[#ef4444]"
          >
            Retry
          </button>
        </div>
      ) : null}

      {orderedMonths.length === 0 && !loading && !errorMessage ? (
        <p className="mt-4 text-sm text-[#64748b]">
          Other expenses become available once active imported months exist in the visible report
          range.
        </p>
      ) : null}

      {expenseTypes.length > 0 ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-2xl border border-[#dbe4f0] bg-[#f8fafc] p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-2">
                {expenseTypes.map((expenseType) => {
                  const enabled = enabledByKey[expenseType.key] ?? false;
                  return (
                    <label
                      key={expenseType.key}
                      className="flex items-center gap-3 text-sm text-[#0f172a]"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setEnabledByKey((current) => ({
                            ...current,
                            [expenseType.key]: !enabled,
                          }))
                        }
                        className={`inline-flex h-6 w-11 items-center rounded-full border transition ${
                          enabled
                            ? "border-[#0a6fd6] bg-[#0a6fd6]"
                            : "border-[#cbd5e1] bg-white"
                        }`}
                        aria-pressed={enabled}
                      >
                        <span
                          className={`ml-0.5 inline-block h-5 w-5 rounded-full bg-white shadow transition ${
                            enabled ? "translate-x-5" : "translate-x-0"
                          }`}
                        />
                      </button>
                      <span className="font-medium">{expenseType.label}</span>
                      <span className="text-xs text-[#64748b]">
                        {enabled ? "Shown in report" : "Hidden from report"}
                      </span>
                    </label>
                  );
                })}
              </div>
              <div className="text-xs text-[#64748b]">
                Toggle each row on or off without deleting the monthly values.
              </div>
            </div>
          </div>

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
                Re-upload the full exported month list to rewrite other expenses safely. Leave a
                cell blank to clear it.
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

          <div className="overflow-x-auto rounded-2xl border border-[#dbe4f0]">
            <table className="min-w-full border-separate border-spacing-0 text-sm">
              <thead>
                <tr>
                  <th className="bg-[#f8fafc] px-4 py-3 text-left font-semibold text-[#334155]">
                    Month
                  </th>
                  {expenseTypes.map((expenseType) => (
                    <th
                      key={expenseType.key}
                      className="bg-[#f8fafc] px-4 py-3 text-left font-semibold text-[#334155]"
                    >
                      {expenseType.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {orderedMonths.map((month) => (
                  <tr key={month.entry_month} className="border-t border-[#e2e8f0]">
                    <td className="whitespace-nowrap bg-white px-4 py-3 font-medium text-[#0f172a]">
                      {formatMonth(month.entry_month)}
                    </td>
                    {expenseTypes.map((expenseType) => (
                      <td key={expenseType.key} className="bg-white px-4 py-3">
                        <label className="flex items-center gap-2">
                          <span className="text-sm text-[#64748b]">$</span>
                          <input
                            type="text"
                            inputMode="decimal"
                            value={drafts[month.entry_month]?.[expenseType.key] ?? ""}
                            onChange={(event) =>
                              setDrafts((current) => ({
                                ...current,
                                [month.entry_month]: {
                                  ...(current[month.entry_month] ?? {}),
                                  [expenseType.key]: event.target.value,
                                },
                              }))
                            }
                            placeholder="0.00"
                            className="w-full rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-sm text-[#0f172a] shadow-inner outline-none transition focus:border-[#0a6fd6] focus:ring-2 focus:ring-[#8cc7ff]/50"
                          />
                        </label>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={loading || saving || importingCsv}
              className="rounded-xl bg-[#0f172a] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#1e293b] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save other expenses"}
            </button>
            {saveMessage ? <p className="text-sm text-[#166534]">{saveMessage}</p> : null}
            {localError ? <p className="text-sm text-[#991b1b]">{localError}</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
