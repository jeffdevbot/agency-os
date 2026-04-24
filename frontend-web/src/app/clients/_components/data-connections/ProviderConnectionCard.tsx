"use client";

import type { SpApiRegionCode } from "@/app/reports/_lib/reportApiAccessApi";

export type ProviderKind = "amazon-ads" | "sp-api";
export type ProviderConnectionState = "not_connected" | "connected" | "error" | "revoked";

type Props = {
  provider: ProviderKind;
  region: SpApiRegionCode;
  state: ProviderConnectionState;
  accountId?: string | null;
  lastValidatedAt?: Date | null;
  errorMessage?: string | null;
  additionalAccountCount?: number;
  actionPending?: boolean;
  advancedHref?: string;
  onConnect(): void;
  onValidate(): void;
  onDisconnect(): void;
};

const providerCopy: Record<ProviderKind, { label: string; accent: string; helper: string }> = {
  "amazon-ads": {
    label: "Amazon Ads",
    accent: "bg-[#FF9900]",
    helper: "Authorize advertising data for this region.",
  },
  "sp-api": {
    label: "SP-API",
    accent: "bg-[#0f766e]",
    helper: "Authorize Seller API data for this region.",
  },
};

const stateStyle: Record<
  ProviderConnectionState,
  { border: string; rail: string; surface: string; label: string; text: string }
> = {
  not_connected: {
    border: "border-slate-200",
    rail: "bg-slate-300",
    surface: "bg-white/80",
    label: "Not connected",
    text: "text-slate-600",
  },
  connected: {
    border: "border-emerald-200",
    rail: "bg-emerald-500",
    surface: "bg-emerald-50/70",
    label: "Connected",
    text: "text-emerald-800",
  },
  error: {
    border: "border-amber-300",
    rail: "bg-amber-500",
    surface: "bg-amber-50/80",
    label: "Needs attention",
    text: "text-amber-900",
  },
  revoked: {
    border: "border-rose-300",
    rail: "bg-rose-500",
    surface: "bg-rose-50/80",
    label: "Revoked",
    text: "text-rose-900",
  },
};

const formatRelativeTime = (date: Date | null | undefined): string => {
  if (!date || Number.isNaN(date.getTime())) return "Never validated";
  const elapsedMs = Date.now() - date.getTime();
  const elapsedMinutes = Math.max(0, Math.round(elapsedMs / 60_000));
  if (elapsedMinutes < 1) return "Validated just now";
  if (elapsedMinutes < 60) return `Validated ${elapsedMinutes}m ago`;
  const elapsedHours = Math.round(elapsedMinutes / 60);
  if (elapsedHours < 48) return `Validated ${elapsedHours}h ago`;
  const elapsedDays = Math.round(elapsedHours / 24);
  return `Validated ${elapsedDays}d ago`;
};

export default function ProviderConnectionCard({
  provider,
  state,
  accountId,
  lastValidatedAt,
  errorMessage,
  additionalAccountCount = 0,
  actionPending = false,
  advancedHref = "#advanced-connection-details",
  onConnect,
  onValidate,
  onDisconnect,
}: Props) {
  const copy = providerCopy[provider];
  const style = stateStyle[state];
  const isConnected = state === "connected";
  const isDisconnected = state === "not_connected";
  const isRevoked = state === "revoked";
  const isError = state === "error";

  return (
    <article
      className={`relative overflow-hidden rounded-2xl border ${style.border} ${style.surface} shadow-sm transition-opacity duration-200 ${
        actionPending ? "opacity-70" : "opacity-100"
      }`}
    >
      <div className={`absolute inset-y-0 left-0 w-1.5 ${style.rail}`} aria-hidden="true" />
      <div className="p-5 pl-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${copy.accent}`} aria-hidden="true" />
              <h3 className="text-base font-semibold text-slate-950">{copy.label}</h3>
            </div>
            <p className={`mt-1 text-sm font-semibold ${style.text}`}>{style.label}</p>
          </div>
          {additionalAccountCount > 0 ? (
            <a href={advancedHref} className="text-xs font-semibold text-slate-500 hover:text-slate-800">
              +{additionalAccountCount} more
            </a>
          ) : null}
        </div>

        {isDisconnected ? (
          <div className="mt-5">
            <p className="min-h-10 text-sm text-slate-600">{copy.helper}</p>
            <button
              type="button"
              onClick={onConnect}
              disabled={actionPending}
              className="mt-4 w-full rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {actionPending ? "Starting..." : `Connect ${copy.label}`}
            </button>
          </div>
        ) : null}

        {isConnected ? (
          <div className="mt-5 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Account</p>
              <p className="mt-1 truncate text-lg font-semibold text-slate-950">
                {accountId || "Connected account"}
              </p>
              <p className="mt-1 text-sm text-slate-600">{formatRelativeTime(lastValidatedAt)}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onValidate}
                disabled={actionPending}
                className="rounded-xl border border-emerald-200 bg-white px-3 py-2 text-sm font-semibold text-emerald-800 transition hover:border-emerald-300 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:text-slate-400"
              >
                {actionPending ? "Working..." : "Validate"}
              </button>
              <button
                type="button"
                onClick={onDisconnect}
                disabled={actionPending}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 transition hover:border-rose-200 hover:text-rose-700 disabled:cursor-not-allowed disabled:text-slate-400"
              >
                Disconnect
              </button>
            </div>
          </div>
        ) : null}

        {isError ? (
          <div className="mt-5 space-y-4">
            <p className="line-clamp-2 text-sm text-amber-950">
              {errorMessage || "Validation failed. Reconnect or validate again."}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onConnect}
                disabled={actionPending}
                className="rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Reconnect
              </button>
              <button
                type="button"
                onClick={onValidate}
                disabled={actionPending}
                className="rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm font-semibold text-amber-900 transition hover:border-amber-300 disabled:cursor-not-allowed disabled:text-slate-400"
              >
                Validate
              </button>
            </div>
          </div>
        ) : null}

        {isRevoked ? (
          <div className="mt-5 space-y-4">
            <p className="text-sm text-rose-950">Access revoked at Amazon. Reconnect to resume ingesting data.</p>
            <button
              type="button"
              onClick={onConnect}
              disabled={actionPending}
              className="rounded-xl bg-rose-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              Reconnect
            </button>
          </div>
        ) : null}
      </div>
    </article>
  );
}
