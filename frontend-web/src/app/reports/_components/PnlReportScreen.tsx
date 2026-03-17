"use client";

import { useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { usePnlActiveImports } from "../pnl/_lib/usePnlActiveImports";
import {
  formatMonthList,
  lastCompletedMonthISO,
  monthsBeforeISO,
} from "../pnl/_lib/pnlDisplay";
import { buildPresentedPnlReport } from "../pnl/_lib/pnlPresentation";
import { useResolvedPnlProfile } from "../pnl/_lib/useResolvedPnlProfile";
import { usePnlReport } from "../pnl/_lib/usePnlReport";
import {
  createPnlProfile,
  getPnlImportSummary,
  uploadPnlTransactionReport,
  type PnlImport,
  type PnlFilterMode,
} from "../pnl/_lib/pnlApi";
import { buildPnlImportProgressLines } from "../pnl/_lib/pnlImportProgress";
import { usePnlOtherExpenses } from "../pnl/_lib/usePnlOtherExpenses";
import { usePnlSkuCogs } from "../pnl/_lib/usePnlSkuCogs";
import { defaultPnlCurrencyCode } from "../pnl/_lib/pnlProfileDefaults";
import type { PnlDisplayMode } from "../pnl/_lib/pnlPresentation";
import { usePnlWorkbookExport } from "../pnl/_lib/usePnlWorkbookExport";
import PnlCogsCard from "./PnlCogsCard";
import PnlOtherExpensesCard from "./PnlOtherExpensesCard";
import PnlProfileSetupCard from "./PnlProfileSetupCard";
import PnlProvenanceCard from "./PnlProvenanceCard";
import PnlReportHeader from "./PnlReportHeader";
import PnlReportTable from "./PnlReportTable";
import PnlUploadCard from "./PnlUploadCard";
import PnlWarningBanner from "./PnlWarningBanner";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function PnlReportScreen({ clientSlug, marketplaceCode }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const resolved = useResolvedPnlProfile(clientSlug, marketplaceCode);
  const defaultRangeEnd = useMemo(() => lastCompletedMonthISO(), []);
  const defaultRangeStart = useMemo(() => monthsBeforeISO(defaultRangeEnd, 2), [defaultRangeEnd]);
  const [filterMode, setFilterMode] = useState<PnlFilterMode>("range");
  const [rangeStart, setRangeStart] = useState<string>(defaultRangeStart);
  const [rangeEnd, setRangeEnd] = useState<string>(defaultRangeEnd);
  const [showSettings, setShowSettings] = useState(false);
  const [displayMode, setDisplayMode] = useState<PnlDisplayMode>("dollars");
  const [showTotals, setShowTotals] = useState(true);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createPending, setCreatePending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processingImportId, setProcessingImportId] = useState<string | null>(null);
  const [processingImport, setProcessingImport] = useState<PnlImport | null>(null);
  const [processingImportStatus, setProcessingImportStatus] = useState<string | null>(null);
  const [processingImportLabel, setProcessingImportLabel] = useState<string | null>(null);

  const profileId = resolved.resolved?.profile?.id ?? null;
  const reportState = usePnlReport(
    profileId,
    filterMode,
    filterMode === "range" ? rangeStart : undefined,
    filterMode === "range" ? rangeEnd : undefined,
  );
  const report = reportState.report;
  const months = report?.months ?? [];
  const lineItems = report?.line_items ?? [];
  const warnings = report?.warnings ?? [];
  const presentedReport = useMemo(
    () => buildPresentedPnlReport(months, lineItems, warnings, displayMode),
    [displayMode, lineItems, months, warnings],
  );
  const provenanceState = usePnlActiveImports(
    showSettings ? profileId : null,
    showSettings ? months : [],
  );
  const workbookExport = usePnlWorkbookExport(profileId);
  const cogsStartMonth = months[0] ?? null;
  const cogsEndMonth = months.length > 0 ? months[months.length - 1] : null;
  const cogsState = usePnlSkuCogs(profileId, cogsStartMonth, cogsEndMonth, showSettings);
  const otherExpensesState = usePnlOtherExpenses(
    profileId,
    cogsStartMonth,
    cogsEndMonth,
    showSettings,
  );
  const processingLines = useMemo(
    () => buildPnlImportProgressLines(processingImport),
    [processingImport],
  );

  useEffect(() => {
    setUploadError(null);
  }, [filterMode, rangeEnd, rangeStart]);

  useEffect(() => {
    if (!profileId || !processingImportId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const pollImport = async () => {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session?.access_token) {
          throw new Error("Please sign in again.");
        }

        const summary = await getPnlImportSummary(
          session.access_token,
          profileId,
          processingImportId,
        );

        if (cancelled) {
          return;
        }

        const status = summary.import.import_status;
        setProcessingImport(summary.import);
        setProcessingImportStatus(status);

        if (status === "pending" || status === "running") {
          timeoutId = window.setTimeout(() => {
            void pollImport();
          }, 5000);
          return;
        }

        setProcessingImportId(null);
        setProcessingImport(null);
        if (status === "success") {
          setUploadSuccess(
            `Finished importing ${processingImportLabel ?? "the queued Amazon P&L upload"}.`,
          );
          setUploadError(null);
        } else {
          setUploadError(summary.import.error_message ?? "Amazon P&L import failed.");
        }
        await reportState.loadReport(true);
        if (showSettings) {
          await Promise.all([
            provenanceState.loadActiveImports(),
            status === "success" ? cogsState.loadSkus() : Promise.resolve(),
            status === "success" ? otherExpensesState.loadOtherExpenses() : Promise.resolve(),
          ]);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setUploadError(
          error instanceof Error
            ? error.message
            : "Unable to refresh Amazon P&L import status",
        );
        timeoutId = window.setTimeout(() => {
          void pollImport();
        }, 5000);
      }
    };

    void pollImport();

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [
    processingImportId,
    processingImportLabel,
    cogsState.loadSkus,
    otherExpensesState.loadOtherExpenses,
    profileId,
    provenanceState.loadActiveImports,
    reportState.loadReport,
    showSettings,
    supabase,
  ]);

  const handleFileChange = (file: File | null) => {
    setSelectedFile(file);
    setUploadError(null);
    setUploadSuccess(null);
  };

  const handleCreateProfile = async () => {
    const resolvedSummary = resolved.resolved;
    if (!resolvedSummary) return;

    setCreatePending(true);
    setCreateError(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) throw new Error("Please sign in again.");

      await createPnlProfile(session.access_token, {
        clientId: resolvedSummary.client.id,
        marketplaceCode: marketplaceCode.toUpperCase(),
        currencyCode: defaultPnlCurrencyCode(marketplaceCode),
      });

      await resolved.loadRoute();
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Unable to create P&L profile");
    } finally {
      setCreatePending(false);
    }
  };

  const handleUpload = async () => {
    if (!profileId || !selectedFile) return;

    setUploadPending(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) throw new Error("Please sign in again.");

      const result = await uploadPnlTransactionReport(session.access_token, profileId, selectedFile);
      const monthLabel = formatMonthList(result.months);
      setUploadSuccess(
        result.import.import_status === "pending"
          ? `Queued ${selectedFile.name} for ${monthLabel}. Processing continues in the background.`
          : `Imported ${selectedFile.name} for ${monthLabel}.`,
      );
      setProcessingImportLabel(`${selectedFile.name} for ${monthLabel}`);
      setSelectedFile(null);
      setProcessingImport(result.import);

      if (result.import.import_status === "pending" || result.import.import_status === "running") {
        setProcessingImportId(result.import.id);
        setProcessingImportStatus(result.import.import_status);
      } else {
        setProcessingImportId(null);
        setProcessingImportStatus(null);
        await reportState.loadReport(true);
        if (showSettings) {
          await Promise.all([
            provenanceState.loadActiveImports(),
            cogsState.loadSkus(),
            otherExpensesState.loadOtherExpenses(),
          ]);
        }
      }
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Unable to upload transaction report");
    } finally {
      setUploadPending(false);
    }
  };

  const handleSaveCogs = async (
    entries: Array<{ sku: string; unit_cost: string | null }>,
  ) => {
    await cogsState.saveSkus(entries);
    await reportState.loadReport(true);
  };

  const handleSaveOtherExpenses = async (payload: {
    expense_types: Array<{ key: string; enabled: boolean }>;
    months: Array<{ entry_month: string; values: Record<string, string | null> }>;
  }) => {
    await otherExpensesState.saveOtherExpenses(payload);
    await reportState.loadReport(true);
  };

  const handleExportWorkbook = async () => {
    if (!profileId) return;
    await workbookExport.downloadWorkbook({
      filterMode,
      startMonth: filterMode === "range" ? rangeStart : undefined,
      endMonth: filterMode === "range" ? rangeEnd : undefined,
      showTotals,
    });
  };

  if (resolved.loading || (profileId !== null && reportState.loading)) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading Amazon P&amp;L report...
        </div>
      </main>
    );
  }

  if (!resolved.resolved) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">Amazon P&amp;L</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to resolve P&L route"}
          </p>
        </div>
      </main>
    );
  }

  const { client, profile } = resolved.resolved;

  return (
    <main className="space-y-3">
      <PnlReportHeader
        clientName={client.name}
        marketplaceCode={marketplaceCode}
        profile={profile}
        filterMode={filterMode}
        rangeStart={rangeStart}
        rangeEnd={rangeEnd}
        settingsOpen={showSettings}
        displayMode={displayMode}
        showTotals={showTotals}
        exportPending={workbookExport.exporting}
        onFilterModeChange={setFilterMode}
        onRangeStartChange={setRangeStart}
        onRangeEndChange={setRangeEnd}
        onToggleSettings={() => setShowSettings((value) => !value)}
        onDisplayModeChange={setDisplayMode}
        onToggleTotals={() => setShowTotals((value) => !value)}
        onExport={() => void handleExportWorkbook()}
      />

      {!profile ? (
        <PnlProfileSetupCard
          marketplaceCode={marketplaceCode}
          createPending={createPending}
          createError={createError}
          onCreateProfile={() => void handleCreateProfile()}
        />
      ) : null}

      {profile && processingImportId ? (
        <div className="rounded-3xl border border-[#0a6fd6]/20 bg-[#eff6ff] px-5 py-4 text-sm text-[#0f172a] shadow-[0_20px_60px_rgba(10,59,130,0.08)] backdrop-blur md:px-6">
          Processing Amazon P&amp;L import in the background.
          {" "}
          Status: <span className="font-semibold capitalize">{processingImportStatus ?? "pending"}</span>.
          {" "}
          The report will refresh automatically when it finishes.
          {processingLines.map((line) => (
            <p key={line} className="mt-1 text-[#334155]">
              {line}
            </p>
          ))}
        </div>
      ) : null}

      {workbookExport.errorMessage ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <p className="rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {workbookExport.errorMessage}
          </p>
        </div>
      ) : null}

      {profile && showSettings ? (
        <div className="rounded-3xl bg-white/95 p-3.5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[#0f172a]">Amazon P&amp;L settings</h2>
              <p className="mt-1 text-sm text-[#64748b]">
                Upload backfill files and inspect the import history for this
                marketplace.
              </p>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            <PnlUploadCard
              selectedFileName={selectedFile?.name ?? null}
              uploadPending={uploadPending}
              uploadError={uploadError}
              uploadSuccess={uploadSuccess}
              processingStatus={processingImportStatus}
              processingLines={processingLines}
              onFileChange={handleFileChange}
              onUpload={() => void handleUpload()}
            />
            <PnlCogsCard
              skus={cogsState.skus}
              loading={cogsState.loading}
              saving={cogsState.saving}
              errorMessage={cogsState.errorMessage}
              onRetry={() => void cogsState.loadSkus()}
              onSave={handleSaveCogs}
            />
            <PnlOtherExpensesCard
              expenseTypes={otherExpensesState.otherExpenses.expense_types}
              months={otherExpensesState.otherExpenses.months}
              loading={otherExpensesState.loading}
              saving={otherExpensesState.saving}
              errorMessage={otherExpensesState.errorMessage}
              onRetry={() => void otherExpensesState.loadOtherExpenses()}
              onSave={handleSaveOtherExpenses}
            />
            <PnlProvenanceCard
              monthsInView={months}
              activeImports={provenanceState.activeImports}
              loading={provenanceState.loading}
              errorMessage={provenanceState.errorMessage}
              onRetry={() => void provenanceState.loadActiveImports()}
            />
          </div>
        </div>
      ) : null}

      {presentedReport.warnings.length > 0 ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="space-y-2">
            {presentedReport.warnings.map((warning, index) => (
              <PnlWarningBanner key={index} warning={warning} />
            ))}
          </div>
        </div>
      ) : null}

      {reportState.errorMessage ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <p className="rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {reportState.errorMessage}
          </p>
        </div>
      ) : null}

      {months.length > 0 && presentedReport.lineItems.length > 0 ? (
        <PnlReportTable
          months={months}
          lineItems={presentedReport.lineItems}
          showTotals={showTotals}
        />
      ) : null}

      {profile && months.length === 0 && !reportState.errorMessage ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <p className="text-sm text-[#64748b]">
            No Amazon P&amp;L data available for the selected period yet. Upload a transaction report to
            backfill this marketplace.
          </p>
        </div>
      ) : null}
    </main>
  );
}
