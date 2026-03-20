"use client";

import { useEffect, useMemo, useState } from "react";
import { getAccessToken } from "@/lib/getAccessToken";
import { usePnlActiveImports } from "../pnl/_lib/usePnlActiveImports";
import {
  formatMonth,
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
import { usePnlWindsorCompare } from "../pnl/_lib/usePnlWindsorCompare";
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
import PnlWindsorCompareCard from "./PnlWindsorCompareCard";
import WbrTrendChart from "./WbrTrendChart";
import { usePnlChartState } from "./usePnlChartState";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function PnlReportScreen({ clientSlug, marketplaceCode }: Props) {
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
  const [windsorCompareMonth, setWindsorCompareMonth] = useState<string>(defaultRangeEnd);
  const [windsorMarketplaceScope, setWindsorMarketplaceScope] = useState<
    "all" | "amazon_com_only" | "amazon_com_and_ca"
  >("all");

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
  const cogsState = usePnlSkuCogs(profileId, showSettings);
  const windsorCompareState = usePnlWindsorCompare(profileId);
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

  const pnlChart = usePnlChartState();
  const CHART_COLORS = ["#0a6fd6", "#f97316", "#14b8a6", "#6366f1", "#f43f5e", "#65a30d"];
  const chartSeries = useMemo(() => {
    const selected = presentedReport.lineItems.filter((item) =>
      pnlChart.selectedRowKeys.has(item.key),
    );
    if (selected.length === 0) return [];

    const series = selected.slice(0, CHART_COLORS.length).map((item, index) => ({
      key: item.key,
      label: item.label,
      data: months.map((month) => {
        const parsed = parseFloat(item.months[month] ?? "0");
        return Number.isFinite(parsed) ? parsed : 0;
      }),
      color: CHART_COLORS[index],
    }));

    if (pnlChart.showTotal && selected.length > 1) {
      const totalData = months.map((_, monthIndex) =>
        series.reduce((sum, s) => sum + s.data[monthIndex], 0),
      );
      series.unshift({
        key: "total",
        label: "Total",
        data: totalData,
        color: "#1e293b",
      });
    }

    return series;
  }, [months, presentedReport.lineItems, pnlChart.selectedRowKeys, pnlChart.showTotal]);

  const chartFormatValue = useMemo(() => {
    const selectedItems = presentedReport.lineItems.filter((item) =>
      pnlChart.selectedRowKeys.has(item.key),
    );
    const allPercent = selectedItems.length > 0 && selectedItems.every((item) => item.display_format === "percent");
    if (allPercent) {
      return (value: number) => `${value.toFixed(1)}%`;
    }
    return (value: number) =>
      new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(value);
  }, [presentedReport.lineItems, pnlChart.selectedRowKeys]);

  useEffect(() => {
    setUploadError(null);
  }, [filterMode, rangeEnd, rangeStart]);

  useEffect(() => {
    if (months.length > 0 && windsorCompareState.loadedMonth === null) {
      setWindsorCompareMonth(months[months.length - 1] || defaultRangeEnd);
    }
  }, [defaultRangeEnd, months, windsorCompareState.loadedMonth]);

  useEffect(() => {
    if (!showSettings) {
      windsorCompareState.resetComparison();
    }
  }, [showSettings, windsorCompareState.resetComparison]);

  useEffect(() => {
    if (!profileId || !processingImportId) {
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const pollImport = async () => {
      try {
        const token = await getAccessToken();

        const summary = await getPnlImportSummary(
          token,
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
      const token = await getAccessToken();

      await createPnlProfile(token, {
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
      const token = await getAccessToken();

      const result = await uploadPnlTransactionReport(token, profileId, selectedFile);
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

  const handleRunWindsorCompare = async () => {
    if (!profileId || !windsorCompareMonth) return;
    try {
      await windsorCompareState.loadComparison(windsorCompareMonth, windsorMarketplaceScope);
    } catch {
      // Error state is already surfaced by the Windsor compare hook.
    }
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
            <PnlWindsorCompareCard
              entryMonth={windsorCompareMonth}
              marketplaceScope={windsorMarketplaceScope}
              comparison={windsorCompareState.comparison}
              loading={windsorCompareState.loading}
              errorMessage={windsorCompareState.errorMessage}
              onEntryMonthChange={setWindsorCompareMonth}
              onMarketplaceScopeChange={setWindsorMarketplaceScope}
              onRunCompare={() => void handleRunWindsorCompare()}
            />
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
        <>
          {chartSeries.length > 0 ? (
            <WbrTrendChart
              title="P&L Trend"
              weeks={months.map((month) => ({ label: formatMonth(month) }))}
              series={chartSeries}
              formatValue={chartFormatValue}
              showTotal={pnlChart.showTotal}
              onToggleTotal={pnlChart.toggleTotal}
            />
          ) : null}
          <PnlReportTable
            months={months}
            lineItems={presentedReport.lineItems}
            showTotals={showTotals}
            selectedRowKeys={pnlChart.selectedRowKeys}
            onRowToggle={pnlChart.toggleRow}
          />
        </>
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
