"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  getSearchTermSyncCoverage,
  listSearchTermSyncRuns,
  type WbrSyncCoverage,
  type WbrSyncRun,
} from "../wbr/_lib/wbrAmazonAdsApi";
import type { WbrProfile } from "../wbr/_lib/wbrApi";
import {
  loadClientReportSurfaceSummaryBySlug,
  type ClientReportSurfaceSummary,
} from "../_lib/reportClientData";
import {
  listSearchTermFacts,
  type SearchTermFact,
  type SearchTermFactsParams,
} from "../_lib/searchTermDataApi";

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

const formatTimestamp = (value: string | null): string => {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
};

const formatCurrency = (value: string | number | null, currencyCode: string | null): string => {
  if (value === null || value === undefined) return "—";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(num)) return String(value);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currencyCode ?? "USD",
    minimumFractionDigits: 2,
  }).format(num);
};

const formatNumber = (value: number): string => value.toLocaleString();

const todayIso = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const daysAgoIso = (n: number): string => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const PAGE_SIZE = 200;

const statusClasses: Record<string, string> = {
  running: "border-sky-200 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
};

// ------------------------------------------------------------------
// Sub-components
// ------------------------------------------------------------------

function StatusPanel({
  latestRun,
  coverage,
  loadingStatus,
}: {
  latestRun: WbrSyncRun | null;
  coverage: WbrSyncCoverage | null;
  loadingStatus: boolean;
}) {
  if (loadingStatus) {
    return (
      <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4 text-sm text-[#64748b]">
        Loading sync status...
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#dbe4f0] bg-[#f7faff] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Sync Status</p>
      <div className="mt-2 flex flex-wrap gap-4 text-sm">
        {latestRun ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[#4c576f]">Latest run:</span>
            <span
              className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClasses[latestRun.status] ?? ""}`}
            >
              {latestRun.status}
            </span>
            <span className="text-[#4c576f]">{formatTimestamp(latestRun.started_at)}</span>
            {latestRun.date_from && latestRun.date_to ? (
              <span className="text-[#64748b]">
                {latestRun.date_from} → {latestRun.date_to}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-[#64748b]">No STR sync runs yet.</span>
        )}
        {coverage ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[#4c576f]">Coverage:</span>
            <span className="text-[#0f172a]">
              {coverage.covered_day_count} day{coverage.covered_day_count !== 1 ? "s" : ""} (
              {coverage.window_start} – {coverage.window_end})
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function FilterBar({
  dateFrom,
  dateTo,
  campaignType,
  campaignNameContains,
  searchTermContains,
  onDateFromChange,
  onDateToChange,
  onCampaignTypeChange,
  onCampaignNameContainsChange,
  onSearchTermContainsChange,
  onApply,
  loading,
}: {
  dateFrom: string;
  dateTo: string;
  campaignType: string;
  campaignNameContains: string;
  searchTermContains: string;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  onCampaignTypeChange: (v: string) => void;
  onCampaignNameContainsChange: (v: string) => void;
  onSearchTermContainsChange: (v: string) => void;
  onApply: () => void;
  loading: boolean;
}) {
  const inputClass =
    "w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">From</span>
          <input
            type="date"
            value={dateFrom}
            max={todayIso()}
            onChange={(e) => onDateFromChange(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">To</span>
          <input
            type="date"
            value={dateTo}
            max={todayIso()}
            onChange={(e) => onDateToChange(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Campaign Type</span>
          <select
            value={campaignType}
            onChange={(e) => onCampaignTypeChange(e.target.value)}
            className={inputClass}
          >
            <option value="">All types</option>
            <option value="sponsored_products">Sponsored Products</option>
            <option value="sponsored_brands">Sponsored Brands</option>
            <option value="sponsored_display">Sponsored Display</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Campaign name</span>
          <input
            type="text"
            value={campaignNameContains}
            placeholder="Filter..."
            onChange={(e) => onCampaignNameContainsChange(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Search term</span>
          <input
            type="text"
            value={searchTermContains}
            placeholder="Filter..."
            onChange={(e) => onSearchTermContainsChange(e.target.value)}
            className={inputClass}
          />
        </label>
      </div>
      <div className="mt-3 flex justify-end">
        <button
          onClick={onApply}
          disabled={loading}
          className="rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(10,111,214,0.3)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
        >
          {loading ? "Loading..." : "Apply Filters"}
        </button>
      </div>
    </div>
  );
}

function FactsTable({
  facts,
  loading,
  hasMore,
  onLoadMore,
}: {
  facts: SearchTermFact[];
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
}) {
  if (loading && facts.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
        Loading data...
      </div>
    );
  }

  if (!loading && facts.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-[#64748b]">
        No search term data found for the selected filters and date range.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-[#f7faff]">
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-[#4c576f]">Date</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-[#4c576f]">Type</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-[#4c576f]">Campaign</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-[#4c576f]">Ad Group</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-[#4c576f]">Search Term</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-[#4c576f]">Match</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-[#4c576f]">Impr.</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-[#4c576f]">Clicks</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-[#4c576f]">Spend</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-[#4c576f]">Orders</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-[#4c576f]">Sales</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {facts.map((fact) => (
              <tr key={fact.id} className="hover:bg-[#f7faff]">
                <td className="whitespace-nowrap px-3 py-2 text-[#4c576f]">{fact.report_date}</td>
                <td className="whitespace-nowrap px-3 py-2 text-[#4c576f]">
                  {fact.campaign_type.replace(/_/g, " ")}
                </td>
                <td className="max-w-[200px] truncate px-3 py-2 text-[#0f172a]" title={fact.campaign_name}>
                  {fact.campaign_name}
                </td>
                <td
                  className="max-w-[160px] truncate px-3 py-2 text-[#4c576f]"
                  title={fact.ad_group_name ?? ""}
                >
                  {fact.ad_group_name ?? "—"}
                </td>
                <td className="max-w-[200px] truncate px-3 py-2 text-[#0f172a]" title={fact.search_term}>
                  {fact.search_term}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-[#4c576f]">{fact.match_type ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-[#4c576f]">
                  {formatNumber(fact.impressions)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-[#4c576f]">
                  {formatNumber(fact.clicks)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-[#0f172a]">
                  {formatCurrency(fact.spend, fact.currency_code)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-[#4c576f]">
                  {formatNumber(fact.orders)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-[#0f172a]">
                  {formatCurrency(fact.sales, fact.currency_code)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore || loading ? (
        <div className="border-t border-slate-200 px-4 py-3">
          <button
            onClick={onLoadMore}
            disabled={loading}
            className="rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-4 py-2 text-sm font-semibold text-[#0a6fd6] transition hover:bg-white disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Loading..." : `Load more (showing ${facts.length.toLocaleString()})`}
          </button>
        </div>
      ) : (
        <div className="border-t border-slate-200 px-4 py-2 text-xs text-[#64748b]">
          {facts.length.toLocaleString()} row{facts.length !== 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------
// Main screen
// ------------------------------------------------------------------

type Props = {
  clientSlug: string;
};

export default function SearchTermDataScreen({ clientSlug }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);

  // Client + marketplace data
  const [summary, setSummary] = useState<ClientReportSurfaceSummary | null>(null);
  const [loadingClient, setLoadingClient] = useState(true);
  const [clientError, setClientError] = useState<string | null>(null);

  // Selected WBR profile
  const wbrProfiles = useMemo(
    () =>
      (summary?.marketplaces ?? [])
        .map((m) => m.wbr_profile)
        .filter((p): p is WbrProfile => p !== null),
    [summary],
  );
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const selectedProfile = useMemo(
    () => wbrProfiles.find((p) => p.id === selectedProfileId) ?? wbrProfiles[0] ?? null,
    [wbrProfiles, selectedProfileId],
  );

  // Sync status
  const [latestRun, setLatestRun] = useState<WbrSyncRun | null>(null);
  const [coverage, setCoverage] = useState<WbrSyncCoverage | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);

  // Filters
  const defaultFrom = useMemo(() => daysAgoIso(30), []);
  const defaultTo = useMemo(() => daysAgoIso(1), []);
  const [dateFrom, setDateFrom] = useState(defaultFrom);
  const [dateTo, setDateTo] = useState(defaultTo);
  const [campaignType, setCampaignType] = useState("");
  const [campaignNameContains, setCampaignNameContains] = useState("");
  const [searchTermContains, setSearchTermContains] = useState("");

  // Facts data
  const [facts, setFacts] = useState<SearchTermFact[]>([]);
  const [loadingFacts, setLoadingFacts] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [factsError, setFactsError] = useState<string | null>(null);
  // Track the params used for the current page so load-more knows the offset
  const [appliedParams, setAppliedParams] = useState<SearchTermFactsParams | null>(null);

  const getToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  // Load client summary
  useEffect(() => {
    void (async () => {
      setLoadingClient(true);
      try {
        const token = await getToken();
        const result = await loadClientReportSurfaceSummaryBySlug(token, clientSlug);
        setSummary(result);
      } catch (err) {
        setClientError(err instanceof Error ? err.message : "Failed to load client data");
      } finally {
        setLoadingClient(false);
      }
    })();
  }, [clientSlug, getToken]);

  // Load sync status when profile changes
  useEffect(() => {
    if (!selectedProfile) return;
    void (async () => {
      setLoadingStatus(true);
      setLatestRun(null);
      setCoverage(null);
      try {
        const token = await getToken();
        const [runs, cov] = await Promise.all([
          listSearchTermSyncRuns(token, selectedProfile.id),
          getSearchTermSyncCoverage(token, selectedProfile.id),
        ]);
        setLatestRun(runs[0] ?? null);
        setCoverage(cov);
      } catch {
        // non-fatal — status panel shows nothing
      } finally {
        setLoadingStatus(false);
      }
    })();
  }, [selectedProfile, getToken]);

  const fetchFacts = useCallback(
    async (params: SearchTermFactsParams, append: boolean) => {
      if (!selectedProfile) return;
      setLoadingFacts(true);
      if (!append) setFactsError(null);
      try {
        const token = await getToken();
        const result = await listSearchTermFacts(token, selectedProfile.id, params);
        setFacts((prev) => (append ? [...prev, ...result.facts] : result.facts));
        setHasMore(result.has_more);
        setAppliedParams(params);
      } catch (err) {
        setFactsError(err instanceof Error ? err.message : "Failed to load search term data");
      } finally {
        setLoadingFacts(false);
      }
    },
    [selectedProfile, getToken],
  );

  const handleApply = useCallback(() => {
    const params: SearchTermFactsParams = {
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      campaign_type: campaignType || undefined,
      campaign_name_contains: campaignNameContains || undefined,
      search_term_contains: searchTermContains || undefined,
      limit: PAGE_SIZE,
      offset: 0,
    };
    void fetchFacts(params, false);
  }, [dateFrom, dateTo, campaignType, campaignNameContains, searchTermContains, fetchFacts]);

  const handleLoadMore = useCallback(() => {
    if (!appliedParams) return;
    void fetchFacts(
      { ...appliedParams, offset: (appliedParams.offset ?? 0) + PAGE_SIZE },
      true,
    );
  }, [appliedParams, fetchFacts]);

  // Auto-run initial query when profile resolves
  const [didInitialLoad, setDidInitialLoad] = useState(false);
  useEffect(() => {
    if (selectedProfile && !didInitialLoad && !loadingClient) {
      setDidInitialLoad(true);
      const params: SearchTermFactsParams = {
        date_from: defaultFrom,
        date_to: defaultTo,
        limit: PAGE_SIZE,
        offset: 0,
      };
      void fetchFacts(params, false);
    }
  }, [selectedProfile, didInitialLoad, loadingClient, defaultFrom, defaultTo, fetchFacts]);

  // Reset initial load flag when profile changes so a new auto-load fires
  useEffect(() => {
    setDidInitialLoad(false);
    setFacts([]);
    setHasMore(false);
    setFactsError(null);
    setAppliedParams(null);
  }, [selectedProfile?.id]);

  const clientName = summary?.client.name ?? clientSlug;

  return (
    <main className="mx-auto max-w-[1400px] px-4 py-8 sm:px-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#0a6fd6]">
            Search Term Data
          </p>
          <h1 className="mt-1 text-2xl font-bold text-[#0f172a]">{clientName}</h1>
          <p className="mt-1 text-sm text-[#4c576f]">
            Inspect raw STR data from Amazon Ads. Use the filters below to slice by date, campaign
            type, or keyword.
          </p>
        </div>
        <Link
          href={`/reports/client-data-access/${clientSlug}`}
          className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-[#4c576f] transition hover:bg-slate-50"
        >
          ← Client Data Access
        </Link>
      </div>

      {clientError ? (
        <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {clientError}
        </p>
      ) : loadingClient ? (
        <p className="mt-6 text-sm text-[#64748b]">Loading client data...</p>
      ) : wbrProfiles.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          No WBR profiles found for this client. Configure a WBR profile and run an STR sync
          before using this surface.
        </p>
      ) : (
        <div className="mt-6 space-y-4">
          {/* Profile selector */}
          {wbrProfiles.length > 1 ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-semibold text-[#0f172a]">Marketplace:</span>
              <div className="flex flex-wrap gap-2">
                {wbrProfiles.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProfileId(p.id)}
                    className={`rounded-xl border px-3 py-1.5 text-sm font-semibold transition ${
                      (selectedProfile?.id ?? wbrProfiles[0]?.id) === p.id
                        ? "border-[#0a6fd6] bg-[#0a6fd6] text-white"
                        : "border-[#c7d8f5] bg-[#f7faff] text-[#0a6fd6] hover:bg-white"
                    }`}
                  >
                    {p.marketplace_code}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-[#4c576f]">
              Marketplace:{" "}
              <span className="font-semibold text-[#0f172a]">
                {selectedProfile?.marketplace_code}
              </span>
            </p>
          )}

          {/* Sync status */}
          <StatusPanel
            latestRun={latestRun}
            coverage={coverage}
            loadingStatus={loadingStatus}
          />

          {/* Filters */}
          <FilterBar
            dateFrom={dateFrom}
            dateTo={dateTo}
            campaignType={campaignType}
            campaignNameContains={campaignNameContains}
            searchTermContains={searchTermContains}
            onDateFromChange={setDateFrom}
            onDateToChange={setDateTo}
            onCampaignTypeChange={setCampaignType}
            onCampaignNameContainsChange={setCampaignNameContains}
            onSearchTermContainsChange={setSearchTermContains}
            onApply={handleApply}
            loading={loadingFacts}
          />

          {/* Error */}
          {factsError ? (
            <p className="rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
              {factsError}
            </p>
          ) : null}

          {/* Table */}
          <FactsTable
            facts={facts}
            loading={loadingFacts}
            hasMore={hasMore}
            onLoadMore={handleLoadMore}
          />
        </div>
      )}
    </main>
  );
}
