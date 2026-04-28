"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import {
  exportSalesMixWorkbook,
  getSalesMixReport,
  type SalesMixReport,
  type SalesMixQuery,
} from "../wbr/_lib/salesMixApi";
import WbrTrendChart from "./WbrTrendChart";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

type Preset = "4w" | "13w" | "26w" | "52w" | "custom";

const PRESET_LABEL: Record<Preset, string> = {
  "4w": "Last 4 weeks",
  "13w": "Last 13 weeks",
  "26w": "Last 26 weeks",
  "52w": "Last 52 weeks",
  custom: "Custom",
};

const PRESET_ORDER: Preset[] = ["4w", "13w", "26w", "52w", "custom"];

const AD_TYPE_OPTIONS: { key: string; label: string }[] = [
  { key: "sponsored_products", label: "SP" },
  { key: "sponsored_brands", label: "SB" },
  { key: "sponsored_display", label: "SD" },
];

const DEFAULT_PRESET: Preset = "13w";

const isoDate = (d: Date): string => d.toISOString().slice(0, 10);

const startOfWeek = (d: Date, weekStartDay: string): Date => {
  const day = d.getUTCDay(); // Sun=0
  const offset = weekStartDay === "monday" ? (day === 0 ? 6 : day - 1) : day;
  const next = new Date(d);
  next.setUTCDate(next.getUTCDate() - offset);
  next.setUTCHours(0, 0, 0, 0);
  return next;
};

const computePresetRange = (
  preset: Preset,
  weekStartDay: string
): { dateFrom: string; dateTo: string } | null => {
  if (preset === "custom") return null;
  const weeks = preset === "4w" ? 4 : preset === "13w" ? 13 : preset === "26w" ? 26 : 52;
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  // Most recent fully-completed week ends yesterday (or earlier if mid-week).
  const currentWeekStart = startOfWeek(today, weekStartDay);
  const lastWeekEnd = new Date(currentWeekStart);
  lastWeekEnd.setUTCDate(lastWeekEnd.getUTCDate() - 1);
  const dateFrom = new Date(lastWeekEnd);
  dateFrom.setUTCDate(dateFrom.getUTCDate() - 7 * weeks + 1);
  return {
    dateFrom: isoDate(dateFrom),
    dateTo: isoDate(lastWeekEnd),
  };
};

const formatCurrency = (value: number): string =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);

const formatCurrencyDetail = (value: number): string =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);

const formatPercent = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
};

const formatDate = (value: string): string => {
  if (!value) return "—";
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(parsed);
};

const parseDecimal = (value: string): number => {
  const parsed = Number.parseFloat(value || "0");
  return Number.isFinite(parsed) ? parsed : 0;
};

export default function SalesMixScreen({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const weekStartDay = resolved.profile?.week_start_day ?? "sunday";

  const [preset, setPreset] = useState<Preset>(DEFAULT_PRESET);
  const initialRange = useMemo(
    () => computePresetRange(DEFAULT_PRESET, weekStartDay)!,
    [weekStartDay]
  );
  const [dateFrom, setDateFrom] = useState<string>(initialRange.dateFrom);
  const [dateTo, setDateTo] = useState<string>(initialRange.dateTo);
  const [parentRowIds, setParentRowIds] = useState<string[]>([]);
  const [adTypes, setAdTypes] = useState<string[]>([]);
  const [report, setReport] = useState<SalesMixReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [chartView, setChartView] = useState<"ads_vs_organic" | "brand_vs_category">(
    "ads_vs_organic"
  );
  const [chartMetric, setChartMetric] = useState<"dollars" | "percent">("dollars");
  const [showTotalLine, setShowTotalLine] = useState(false);
  const [tableExpanded, setTableExpanded] = useState(false);

  // Re-snap dates when preset changes (or profile loads with a new week_start_day).
  useEffect(() => {
    if (preset === "custom") return;
    const range = computePresetRange(preset, weekStartDay);
    if (!range) return;
    setDateFrom(range.dateFrom);
    setDateTo(range.dateTo);
  }, [preset, weekStartDay]);

  const getToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  const buildQuery = useCallback(
    (): SalesMixQuery => ({
      dateFrom,
      dateTo,
      parentRowIds: parentRowIds.length ? parentRowIds : undefined,
      adTypes: adTypes.length ? adTypes : undefined,
    }),
    [adTypes, dateFrom, dateTo, parentRowIds]
  );

  const dateRangeInvalid = Boolean(dateFrom && dateTo && dateFrom > dateTo);

  const reload = useCallback(async () => {
    if (!resolved.profile?.id) return;
    if (dateRangeInvalid) {
      setErrorMessage("End date must be on or after start date.");
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getToken();
      const next = await getSalesMixReport(token, resolved.profile.id, buildQuery());
      setReport(next);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load Sales Mix");
    } finally {
      setLoading(false);
    }
  }, [buildQuery, dateRangeInvalid, getToken, resolved.profile?.id]);

  useEffect(() => {
    if (resolved.profile?.id && dateFrom && dateTo && !dateRangeInvalid) {
      void reload();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    resolved.profile?.id,
    dateFrom,
    dateTo,
    dateRangeInvalid,
    parentRowIds.join("|"),
    adTypes.join("|"),
  ]);

  const handleExport = useCallback(async () => {
    if (!resolved.profile?.id || exporting) return;
    setExporting(true);
    setErrorMessage(null);
    try {
      const token = await getToken();
      const { blob, filename } = await exportSalesMixWorkbook(
        token,
        resolved.profile.id,
        buildQuery()
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to export Sales Mix");
    } finally {
      setExporting(false);
    }
  }, [buildQuery, exporting, getToken, resolved.profile?.id]);

  const totals = report?.totals;
  const totalBusiness = totals ? parseDecimal(totals.business_sales) : 0;
  const totalAds = totals ? parseDecimal(totals.ad_sales) : 0;
  const totalOrganic = totals ? parseDecimal(totals.organic_sales) : 0;
  const totalBrand = totals ? parseDecimal(totals.brand_sales) : 0;
  const totalCategory = totals ? parseDecimal(totals.category_sales) : 0;
  const totalUnmappedAds = totals ? parseDecimal(totals.unmapped_ad_sales) : 0;

  const ratioOf = (numerator: number, denominator: number): number =>
    denominator > 0 ? numerator / denominator : 0;

  const chartSeries = useMemo(() => {
    if (!report || report.weekly.length === 0) return [];

    if (chartView === "ads_vs_organic") {
      if (chartMetric === "percent") {
        return [
          {
            key: "organic_share",
            label: "Organic %",
            data: report.weekly.map((w) =>
              ratioOf(parseDecimal(w.organic_sales), parseDecimal(w.business_sales))
            ),
            color: "#10b981",
          },
          {
            key: "ad_share",
            label: "Ads %",
            data: report.weekly.map((w) =>
              ratioOf(parseDecimal(w.ad_sales), parseDecimal(w.business_sales))
            ),
            color: "#0a6fd6",
          },
        ];
      }
      const series = [
        {
          key: "organic_sales",
          label: "Organic Sales",
          data: report.weekly.map((w) => parseDecimal(w.organic_sales)),
          color: "#10b981",
        },
        {
          key: "ad_sales",
          label: "Ad Sales",
          data: report.weekly.map((w) => parseDecimal(w.ad_sales)),
          color: "#0a6fd6",
        },
      ];
      if (showTotalLine) {
        series.push({
          key: "total",
          label: "Total Sales",
          data: report.weekly.map((w) => parseDecimal(w.business_sales)),
          color: "#0f172a",
        });
      }
      return series;
    }

    // Brand vs Category view
    if (chartMetric === "percent") {
      return [
        {
          key: "brand_share",
          label: "Brand %",
          data: report.weekly.map((w) =>
            ratioOf(parseDecimal(w.brand_sales), parseDecimal(w.ad_sales))
          ),
          color: "#7c3aed",
        },
        {
          key: "category_share",
          label: "Category %",
          data: report.weekly.map((w) =>
            ratioOf(parseDecimal(w.category_sales), parseDecimal(w.ad_sales))
          ),
          color: "#0a6fd6",
        },
        {
          key: "unmapped_share",
          label: "Unmapped %",
          data: report.weekly.map((w) =>
            ratioOf(parseDecimal(w.unmapped_ad_sales), parseDecimal(w.ad_sales))
          ),
          color: "#f59e0b",
          dashed: true,
        },
      ];
    }
    const series = [
      {
        key: "brand_sales",
        label: "Brand Sales",
        data: report.weekly.map((w) => parseDecimal(w.brand_sales)),
        color: "#7c3aed",
      },
      {
        key: "category_sales",
        label: "Category Sales",
        data: report.weekly.map((w) => parseDecimal(w.category_sales)),
        color: "#0a6fd6",
      },
      {
        key: "unmapped_ad_sales",
        label: "Unmapped Ads",
        data: report.weekly.map((w) => parseDecimal(w.unmapped_ad_sales)),
        color: "#f59e0b",
        dashed: true,
      },
    ];
    if (showTotalLine) {
      series.push({
        key: "total",
        label: "Total Ad Sales",
        data: report.weekly.map((w) => parseDecimal(w.ad_sales)),
        color: "#0f172a",
      });
    }
    return series;
  }, [chartMetric, chartView, report, showTotalLine]);

  const chartTitle =
    chartView === "ads_vs_organic" ? "Ads vs Organic" : "Brand vs Category";

  const formatPercentChart = (value: number): string => {
    if (!Number.isFinite(value)) return "0%";
    return `${(value * 100).toFixed(1)}%`;
  };

  const profileName = resolved.profile?.display_name ?? clientSlug;
  const profileMarket =
    (resolved.profile?.marketplace_code ?? marketplaceCode).toUpperCase();
  const hasWeeks = Boolean(report && report.weekly.length > 0);
  const showEmptyWindow = Boolean(
    report && !loading && report.weekly.length === 0 && !dateRangeInvalid
  );

  const toggleParent = (id: string) => {
    setParentRowIds((prev) =>
      prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id]
    );
  };

  const toggleAdType = (key: string) => {
    setAdTypes((prev) =>
      prev.includes(key) ? prev.filter((value) => value !== key) : [...prev, key]
    );
  };

  const parentOptions = report?.parent_row_options ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#4c576f]">Report</p>
          <h1 className="text-3xl font-semibold text-[#0f172a]">Sales Mix</h1>
          <p className="mt-1 text-sm text-[#4c576f]">
            {profileName} ({profileMarket}) — Ads vs Organic, Brand vs Category.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void reload()}
            disabled={loading || !resolved.profile?.id}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-[#0a6fd6] transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
          <button
            type="button"
            onClick={() => void handleExport()}
            disabled={exporting || loading || !resolved.profile?.id || !hasWeeks || dateRangeInvalid}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
          >
            {exporting ? "Exporting..." : "Export .xlsx"}
          </button>
        </div>
      </header>

      <section className="rounded-3xl bg-white/95 p-4 shadow-[0_30px_80px_rgba(10,59,130,0.12)] backdrop-blur md:p-5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-2xl border border-slate-200 bg-slate-50 p-1 text-xs font-semibold">
            {PRESET_ORDER.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setPreset(value)}
                className={
                  preset === value
                    ? "rounded-xl bg-white px-3 py-1.5 text-[#0a6fd6] shadow-sm"
                    : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
                }
              >
                {PRESET_LABEL[value]}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 text-sm">
            <label className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              From
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setPreset("custom");
              }}
              className="rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-sm text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
            />
            <label className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              To
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(event) => {
                setDateTo(event.target.value);
                setPreset("custom");
              }}
              className="rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-sm text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              Ad type
            </span>
            <div className="inline-flex flex-wrap gap-1">
              {AD_TYPE_OPTIONS.map((option) => {
                const active = adTypes.includes(option.key);
                return (
                  <button
                    key={option.key}
                    type="button"
                    onClick={() => toggleAdType(option.key)}
                    className={
                      active
                        ? "rounded-full border border-[#0a6fd6] bg-[#0a6fd6] px-3 py-1 text-xs font-semibold text-white"
                        : "rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-[#475569] hover:border-[#0a6fd6] hover:text-[#0a6fd6]"
                    }
                  >
                    {option.label}
                  </button>
                );
              })}
              {adTypes.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setAdTypes([])}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-[#475569] hover:text-rose-600"
                >
                  Clear
                </button>
              ) : null}
            </div>
          </div>
        </div>

        {parentOptions.length > 0 ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              Brands
            </span>
            <div className="inline-flex flex-wrap gap-1">
              {parentOptions.map((option) => {
                const active = parentRowIds.includes(option.id);
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => toggleParent(option.id)}
                    className={
                      active
                        ? "rounded-full border border-violet-500 bg-violet-500 px-3 py-1 text-xs font-semibold text-white"
                        : "rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-[#475569] hover:border-violet-500 hover:text-violet-600"
                    }
                  >
                    {option.row_label || option.id}
                  </button>
                );
              })}
              {parentRowIds.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setParentRowIds([])}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-[#475569] hover:text-rose-600"
                >
                  Clear
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      {dateRangeInvalid ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          End date must be on or after start date.
        </p>
      ) : null}

      {errorMessage ? (
        <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {errorMessage}
        </p>
      ) : null}

      {showEmptyWindow ? (
        <p className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-[#78350f]">
          The selected window contains no fully-completed weeks. Pick an earlier start
          date or use one of the presets above.
        </p>
      ) : null}

      {report?.coverage.warnings?.length ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-[#78350f]">
          <p className="font-semibold">Coverage warnings</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {report.coverage.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiTile label="Total Sales" value={formatCurrency(totalBusiness)} hint={`${report?.weekly.length ?? 0} weeks`} />
        <KpiTile
          label="Ad Sales"
          value={formatCurrency(totalAds)}
          hint={`${formatPercent(totals?.ads_share_of_business_pct)} of business`}
        />
        <KpiTile
          label="Organic Sales"
          value={formatCurrency(totalOrganic)}
          hint={
            totalBusiness > 0
              ? `${formatPercent(1 - (totals?.ads_share_of_business_pct ?? 0))} of business`
              : ""
          }
        />
        <KpiTile
          label="Brand Sales"
          value={formatCurrency(totalBrand)}
          hint={
            totalAds > 0
              ? `${((totalBrand / totalAds) * 100).toFixed(1)}% of ads · Cat ${formatCurrency(totalCategory)}`
              : ""
          }
        />
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-2xl border border-slate-200 bg-slate-50 p-1 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setChartView("ads_vs_organic")}
              className={
                chartView === "ads_vs_organic"
                  ? "rounded-xl bg-white px-3 py-1.5 text-[#0a6fd6] shadow-sm"
                  : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
              }
            >
              Ads vs Organic
            </button>
            <button
              type="button"
              onClick={() => setChartView("brand_vs_category")}
              className={
                chartView === "brand_vs_category"
                  ? "rounded-xl bg-white px-3 py-1.5 text-[#7c3aed] shadow-sm"
                  : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
              }
            >
              Brand vs Category
            </button>
          </div>

          <div className="inline-flex rounded-2xl border border-slate-200 bg-slate-50 p-1 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setChartMetric("dollars")}
              className={
                chartMetric === "dollars"
                  ? "rounded-xl bg-white px-3 py-1.5 text-[#0f172a] shadow-sm"
                  : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
              }
            >
              $
            </button>
            <button
              type="button"
              onClick={() => setChartMetric("percent")}
              className={
                chartMetric === "percent"
                  ? "rounded-xl bg-white px-3 py-1.5 text-[#0f172a] shadow-sm"
                  : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
              }
            >
              %
            </button>
          </div>
          {chartMetric === "percent" ? (
            <span className="text-xs text-[#64748b]">
              {chartView === "ads_vs_organic"
                ? "Series shown as % of business sales (sums to 100% per week)."
                : "Series shown as % of total ad sales (sums to 100% per week)."}
            </span>
          ) : null}
        </div>

        <WbrTrendChart
          title={chartTitle}
          weeks={report?.weekly.map((w) => ({ label: w.label })) ?? []}
          series={chartSeries}
          formatValue={chartMetric === "percent" ? formatPercentChart : formatCurrency}
          showTotal={chartMetric === "dollars" && showTotalLine}
          onToggleTotal={
            chartMetric === "dollars"
              ? () => setShowTotalLine((value) => !value)
              : () => undefined
          }
        />
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white/95 shadow-[0_30px_80px_rgba(10,59,130,0.12)]">
        <button
          type="button"
          onClick={() => setTableExpanded((value) => !value)}
          className="flex w-full items-center justify-between gap-3 rounded-3xl px-5 py-4 text-left transition hover:bg-slate-50"
        >
          <div>
            <p className="text-sm font-semibold text-[#0f172a]">Weekly detail</p>
            <p className="mt-1 text-xs text-[#4c576f]">
              {report?.weekly.length ?? 0} weeks · click to expand
              {totalUnmappedAds > 0
                ? ` · ${formatCurrencyDetail(totalUnmappedAds)} ad sales currently unmapped`
                : ""}
            </p>
          </div>
          <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-[#0a6fd6]">
            {tableExpanded ? "Collapse" : "Expand"}
          </span>
        </button>

        {tableExpanded && report ? (
          <div className="overflow-x-auto px-5 pb-5">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-[#475569]">
                  <th className="px-2 py-2">Week</th>
                  <th className="px-2 py-2 text-right">Total Sales</th>
                  <th className="px-2 py-2 text-right">Ad Sales</th>
                  <th className="px-2 py-2 text-right">Organic</th>
                  <th className="px-2 py-2 text-right">Brand</th>
                  <th className="px-2 py-2 text-right">Category</th>
                  <th className="px-2 py-2 text-right">Unmapped Ads</th>
                  <th className="px-2 py-2 text-right">Ads %</th>
                  <th className="px-2 py-2 text-right">Map %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.weekly.map((week) => {
                  const business = parseDecimal(week.business_sales);
                  const ads = parseDecimal(week.ad_sales);
                  const adsPct = business > 0 ? ads / business : 0;
                  const flagged = week.coverage.below_threshold || !week.coverage.data_present;
                  const flagReason = !week.coverage.data_present
                    ? "No ad-fact rows for this week"
                    : week.coverage.below_threshold
                      ? "Mapping coverage is below the warning threshold"
                      : "";
                  return (
                    <tr
                      key={week.start}
                      title={flagReason || undefined}
                      className={flagged ? "bg-amber-50/60 align-top" : "align-top"}
                    >
                      <td className="px-2 py-2 text-[#0f172a]">{week.label}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                        {formatCurrencyDetail(business)}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                        {formatCurrencyDetail(ads)}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-[#475569]">
                        {formatCurrencyDetail(parseDecimal(week.organic_sales))}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-violet-700">
                        {formatCurrencyDetail(parseDecimal(week.brand_sales))}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                        {formatCurrencyDetail(parseDecimal(week.category_sales))}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-amber-700">
                        {formatCurrencyDetail(parseDecimal(week.unmapped_ad_sales))}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-[#475569]">
                        {formatPercent(adsPct)}
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-[#475569]">
                        {formatPercent(week.coverage.mapping_coverage_pct)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-[#64748b]">
              Window: {formatDate(report.date_from)} → {formatDate(report.date_to)}.
              Amber rows fall below the {(report.coverage.warn_threshold_pct * 100).toFixed(0)}%
              mapping-coverage threshold or have no ad facts that week.
            </p>
          </div>
        ) : null}
      </section>

      {resolved.errorMessage ? (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {resolved.errorMessage}
        </p>
      ) : null}
    </div>
  );
}

type KpiTileProps = {
  label: string;
  value: string;
  hint?: string;
};

function KpiTile({ label, value, hint }: KpiTileProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_15px_30px_rgba(10,59,130,0.08)]">
      <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[#0f172a]">{value}</p>
      {hint ? <p className="mt-1 text-xs text-[#64748b]">{hint}</p> : null}
    </div>
  );
}
