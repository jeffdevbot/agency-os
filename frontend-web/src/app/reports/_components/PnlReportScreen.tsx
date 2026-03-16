"use client";

import { useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { usePnlActiveImports } from "../pnl/_lib/usePnlActiveImports";
import {
  currentMonthISO,
  formatMonthList,
  monthsAgoISO,
} from "../pnl/_lib/pnlDisplay";
import { buildPresentedPnlReport } from "../pnl/_lib/pnlPresentation";
import { useResolvedPnlProfile } from "../pnl/_lib/useResolvedPnlProfile";
import { usePnlReport } from "../pnl/_lib/usePnlReport";
import {
  createPnlProfile,
  uploadPnlTransactionReport,
  type PnlFilterMode,
} from "../pnl/_lib/pnlApi";
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
  const [filterMode, setFilterMode] = useState<PnlFilterMode>("last_3");
  const [rangeStart, setRangeStart] = useState<string>(monthsAgoISO(2));
  const [rangeEnd, setRangeEnd] = useState<string>(currentMonthISO());
  const [showSettings, setShowSettings] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createPending, setCreatePending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

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
    () => buildPresentedPnlReport(months, lineItems, warnings),
    [lineItems, months, warnings],
  );
  const provenanceState = usePnlActiveImports(
    showSettings ? profileId : null,
    showSettings ? months : [],
  );

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
        currencyCode: "USD",
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
      setUploadSuccess(
        `Imported ${selectedFile.name} for ${formatMonthList(result.months)}.`,
      );
      setSelectedFile(null);
      await reportState.loadReport(true);
      if (showSettings) {
        await provenanceState.loadActiveImports();
      }
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Unable to upload transaction report");
    } finally {
      setUploadPending(false);
    }
  };

  if (resolved.loading || (profileId !== null && reportState.loading)) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading P&L report...
        </div>
      </main>
    );
  }

  if (!resolved.resolved) {
    return (
      <main className="space-y-3">
        <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">Monthly P&L</h1>
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
        refreshing={reportState.refreshing}
        settingsOpen={showSettings}
        onFilterModeChange={setFilterMode}
        onRangeStartChange={setRangeStart}
        onRangeEndChange={setRangeEnd}
        onRefresh={() => void reportState.loadReport(true)}
        onToggleSettings={() => setShowSettings((value) => !value)}
      />

      {!profile ? (
        <PnlProfileSetupCard
          marketplaceCode={marketplaceCode}
          createPending={createPending}
          createError={createError}
          onCreateProfile={() => void handleCreateProfile()}
        />
      ) : null}

      {profile && showSettings ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[#0f172a]">Monthly P&amp;L settings</h2>
              <p className="mt-1 text-sm text-[#64748b]">
                Upload backfill files and inspect the active import provenance for this
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
              onFileChange={setSelectedFile}
              onUpload={() => void handleUpload()}
            />
            <PnlProvenanceCard
              monthsInView={months}
              activeImports={provenanceState.activeImports}
              loading={provenanceState.loading}
              errorMessage={provenanceState.errorMessage}
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
        <PnlReportTable months={months} lineItems={presentedReport.lineItems} />
      ) : null}

      {profile && months.length === 0 && !reportState.errorMessage ? (
        <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
          <p className="text-sm text-[#64748b]">
            No P&amp;L data available for the selected period yet. Upload a transaction report to
            backfill this marketplace.
          </p>
        </div>
      ) : null}
    </main>
  );
}
