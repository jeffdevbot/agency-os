"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  createAmazonAdsAuthorizationUrl,
  createSpApiAuthorizationUrl,
  disconnectAmazonAdsConnection,
  disconnectSpApiConnection,
  listAmazonAdsApiAccess,
  listSpApiConnections,
  validateAmazonAdsConnection,
  validateSpApiConnection,
  type AmazonAdsApiAccessSummary,
  type ReportApiAccessSharedConnection,
  type SpApiConnectionSummary,
  type SpApiRegionCode,
} from "@/app/reports/_lib/reportApiAccessApi";
import RegionBlock from "./RegionBlock";
import type { ConnectionCardModel } from "./ConnectionsStrip";
import type { ProviderConnectionState, ProviderKind } from "./ProviderConnectionCard";

type Props = {
  clientId: string;
  clientSlug: string;
};

const REGIONS: Array<{ code: SpApiRegionCode; unlockedMarketplaces: string }> = [
  { code: "NA", unlockedMarketplaces: "Unlocks CA, US, MX" },
  {
    code: "EU",
    unlockedMarketplaces: "Unlocks UK, DE, FR, IT, ES, NL, SE, PL, TR, BE, EG, SA, ZA, AE",
  },
  { code: "FE", unlockedMarketplaces: "Unlocks AU, JP, SG, IN" },
];

const actionKey = (region: SpApiRegionCode, provider: ProviderKind): string => `${region}:${provider}`;

const toDate = (value: string | null | undefined): Date | null => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const timestampValue = (row: ReportApiAccessSharedConnection): number => {
  const value = row.last_validated_at ?? row.updated_at ?? row.connected_at;
  return value ? Date.parse(value) || 0 : 0;
};

const uniqueConnections = (
  rows: ReportApiAccessSharedConnection[],
): ReportApiAccessSharedConnection[] => {
  const byKey = new Map<string, ReportApiAccessSharedConnection>();
  rows.forEach((row, index) => {
    byKey.set(row.id || `${row.provider}:${row.region_code ?? "unknown"}:${index}`, row);
  });
  return [...byKey.values()];
};

const rowsForRegion = (
  rows: ReportApiAccessSharedConnection[],
  region: SpApiRegionCode,
): ReportApiAccessSharedConnection[] =>
  rows
    .filter((row) => row.region_code === region)
    .sort((left, right) => timestampValue(right) - timestampValue(left));

const asConnectionState = (
  rows: ReportApiAccessSharedConnection[],
): ConnectionCardModel => {
  const primary = rows[0];
  if (!primary) {
    return { state: "not_connected" };
  }

  const status = primary.connection_status;
  const state: ProviderConnectionState =
    status === "connected" || status === "error" || status === "revoked"
      ? status
      : "error";

  return {
    state,
    accountId: primary.external_account_id || primary.lwa_account_hint,
    lastValidatedAt: toDate(primary.last_validated_at),
    errorMessage: primary.last_error,
    additionalAccountCount: Math.max(0, rows.length - 1),
  };
};

export default function ClientDataConnectionsOrchestrator({ clientId, clientSlug }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const searchParams = useSearchParams();
  const [adsSummary, setAdsSummary] = useState<AmazonAdsApiAccessSummary | null>(null);
  const [spApiSummary, setSpApiSummary] = useState<SpApiConnectionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const returnPath = `/clients/${clientSlug}/data`;

  const loadConnections = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const [adsRows, spApiRows] = await Promise.all([
        listAmazonAdsApiAccess(session.access_token),
        listSpApiConnections(session.access_token),
      ]);
      setAdsSummary(adsRows.find((summary) => summary.client_id === clientId) ?? null);
      setSpApiSummary(spApiRows.find((summary) => summary.client_id === clientId) ?? null);
    } catch (error) {
      setAdsSummary(null);
      setSpApiSummary(null);
      setErrorMessage(error instanceof Error ? error.message : "Unable to load connections.");
    } finally {
      setLoading(false);
    }
  }, [clientId, supabase]);

  useEffect(() => {
    void loadConnections();
  }, [loadConnections]);

  useEffect(() => {
    const spApiError = searchParams.get("spapi_error");
    const adsError = searchParams.get("amazon_ads_error");
    const error = spApiError || adsError;
    if (!error) return;
    setErrorMessage(error.replace(/_/g, " "));
  }, [searchParams]);

  const getToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }
    return session.access_token;
  }, [supabase]);

  const handleConnect = useCallback(
    async (provider: ProviderKind, region: SpApiRegionCode) => {
      setPendingAction(actionKey(region, provider));
      setErrorMessage(null);
      try {
        const token = await getToken();
        if (provider === "amazon-ads") {
          const profileId = adsSummary?.connect_profiles.find((profile) => profile.status === "active")?.profile_id
            ?? adsSummary?.connect_profiles[0]?.profile_id;
          if (!profileId) {
            throw new Error("Create a marketplace profile before connecting Amazon Ads.");
          }
          const url = await createAmazonAdsAuthorizationUrl(token, profileId, returnPath, region);
          window.location.assign(url);
          return;
        }

        const url = await createSpApiAuthorizationUrl(token, clientId, region, returnPath);
        window.location.assign(url);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Unable to start connection.");
        setPendingAction(null);
      }
    },
    [adsSummary, clientId, getToken, returnPath],
  );

  const handleValidate = useCallback(
    async (provider: ProviderKind, region: SpApiRegionCode) => {
      setPendingAction(actionKey(region, provider));
      setErrorMessage(null);
      try {
        const token = await getToken();
        if (provider === "amazon-ads") {
          await validateAmazonAdsConnection(token, { clientId, region });
        } else {
          await validateSpApiConnection(token, clientId, region);
        }
        await loadConnections();
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Validation failed.");
      } finally {
        setPendingAction(null);
      }
    },
    [clientId, getToken, loadConnections],
  );

  const handleDisconnect = useCallback(
    async (provider: ProviderKind, region: SpApiRegionCode) => {
      const label = provider === "amazon-ads" ? "Amazon Ads" : "SP-API";
      if (!window.confirm(`Disconnect ${label} for ${region}? This preserves the row and revokes stored tokens.`)) {
        return;
      }

      setPendingAction(actionKey(region, provider));
      setErrorMessage(null);
      try {
        const token = await getToken();
        if (provider === "amazon-ads") {
          await disconnectAmazonAdsConnection(token, { clientId, region });
        } else {
          await disconnectSpApiConnection(token, { clientId, region });
        }
        await loadConnections();
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Disconnect failed.");
      } finally {
        setPendingAction(null);
      }
    },
    [clientId, getToken, loadConnections],
  );

  const adsConnections = uniqueConnections([
    ...(adsSummary?.shared_connections ?? []),
    ...(adsSummary?.shared_connection ? [adsSummary.shared_connection] : []),
  ]);
  const spApiConnections = uniqueConnections([
    ...(spApiSummary?.connections ?? []),
    ...(spApiSummary?.connection ? [spApiSummary.connection] : []),
  ]);

  return (
    <section className="space-y-4" aria-busy={loading}>
      <div className="rounded-3xl border border-white/70 bg-white/70 p-6 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Data access</p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">Connections by region</h1>
          </div>
          <button
            type="button"
            onClick={() => void loadConnections()}
            disabled={loading}
            className="self-start rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:text-slate-400 md:self-auto"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-900">
            {errorMessage}
          </p>
        ) : null}
      </div>

      {REGIONS.map(({ code, unlockedMarketplaces }) => {
        const regionAdsRows = rowsForRegion(adsConnections, code);
        const regionSpApiRows = rowsForRegion(spApiConnections, code);
        return (
          <RegionBlock
            key={code}
            region={code}
            unlockedMarketplaces={unlockedMarketplaces}
            adsConnection={asConnectionState(regionAdsRows)}
            spApiConnection={asConnectionState(regionSpApiRows)}
            hasAnyConnection={regionAdsRows.length > 0 || regionSpApiRows.length > 0}
            pendingAction={pendingAction}
            onConnect={handleConnect}
            onValidate={handleValidate}
            onDisconnect={handleDisconnect}
          />
        );
      })}
    </section>
  );
}
