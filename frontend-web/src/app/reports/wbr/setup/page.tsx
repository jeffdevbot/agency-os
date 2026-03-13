"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { slugifyClientName } from "../../_lib/reportClientData";
import { createWbrProfile } from "../_lib/wbrApi";

type Client = {
  id: string;
  name: string;
  status: string;
};

type ClientsResponse = {
  clients?: Client[];
  error?: {
    message?: string;
  };
};

export default function WbrSetupPage() {
  const router = useRouter();
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [marketplaceCode, setMarketplaceCode] = useState("US");
  const [displayName, setDisplayName] = useState("");
  const [weekStartDay, setWeekStartDay] = useState<"sunday" | "monday">("sunday");
  const [windsorAccountId, setWindsorAccountId] = useState("");
  const [amazonAdsProfileId, setAmazonAdsProfileId] = useState("");
  const [amazonAdsAccountId, setAmazonAdsAccountId] = useState("");
  const [backfillStartDate, setBackfillStartDate] = useState("");
  const [dailyRewriteDays, setDailyRewriteDays] = useState("14");

  useEffect(() => {
    fetch("/api/command-center/clients", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as ClientsResponse;
        if (!response.ok) {
          setErrorMessage(json.error?.message ?? "Unable to load clients");
          setClients([]);
          setLoading(false);
          return;
        }
        const active = (json.clients ?? []).filter((client) => client.status !== "archived");
        setClients(active);
        if (active.length > 0) {
          setSelectedClientId(active[0].id);
          setDisplayName(active[0].name);
        }
        setLoading(false);
      })
      .catch(() => {
        setErrorMessage("Unable to load clients");
        setClients([]);
        setLoading(false);
      });
  }, []);

  const selectedClient = useMemo(
    () => clients.find((client) => client.id === selectedClientId) ?? null,
    [clients, selectedClientId]
  );

  useEffect(() => {
    if (!selectedClient) return;
    if (displayName.trim().length > 0) return;
    setDisplayName(selectedClient.name);
  }, [displayName, selectedClient]);

  const submitDisabled =
    loading ||
    saving ||
    !selectedClientId ||
    marketplaceCode.trim() === "" ||
    displayName.trim() === "";

  const optionalInput = (value: string): string | undefined => {
    const trimmed = value.trim();
    return trimmed === "" ? undefined : trimmed;
  };

  const handleCreateProfile = async () => {
    if (submitDisabled) return;

    const rewriteDays = Number(dailyRewriteDays);
    if (!Number.isInteger(rewriteDays) || rewriteDays < 1 || rewriteDays > 60) {
      setErrorMessage("Daily rewrite days must be an integer between 1 and 60.");
      return;
    }

    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session?.access_token) {
        throw new Error("Please sign in again.");
      }

      const created = await createWbrProfile(session.access_token, {
        client_id: selectedClientId,
        marketplace_code: marketplaceCode.trim().toUpperCase(),
        display_name: displayName.trim(),
        week_start_day: weekStartDay,
        windsor_account_id: optionalInput(windsorAccountId),
        amazon_ads_profile_id: optionalInput(amazonAdsProfileId),
        amazon_ads_account_id: optionalInput(amazonAdsAccountId),
        backfill_start_date: optionalInput(backfillStartDate),
        daily_rewrite_days: rewriteDays,
      });

      setSuccessMessage("WBR profile created. Redirecting to workspace...");
      const clientSlug = slugifyClientName(selectedClient?.name ?? displayName.trim());
      router.push(`/reports/${clientSlug}/${created.marketplace_code.toLowerCase()}/wbr/settings`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create WBR profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Setup New WBR Profile</h1>
        <p className="mt-2 text-sm text-[#4c576f]">Create a profile for one client and marketplace.</p>

        <div className="mt-6 grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 md:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Client</span>
            {loading ? (
              <span className="text-[#4c576f]">Loading clients...</span>
            ) : clients.length === 0 ? (
              <span className="text-[#4c576f]">No active clients available.</span>
            ) : (
              <select
                value={selectedClientId}
                onChange={(event) => {
                  setSelectedClientId(event.target.value);
                  const next = clients.find((client) => client.id === event.target.value);
                  if (next) {
                    setDisplayName(next.name);
                  }
                }}
                className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
              >
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            )}
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Marketplace Code</span>
            <input
              value={marketplaceCode}
              onChange={(event) => setMarketplaceCode(event.target.value.toUpperCase())}
              placeholder="US"
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>

          <label className="text-sm md:col-span-2">
            <span className="mb-1 block font-semibold text-[#0f172a]">Display Name</span>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Client Name - US WBR"
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Week Start Day</span>
            <select
              value={weekStartDay}
              onChange={(event) => setWeekStartDay(event.target.value as "sunday" | "monday")}
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            >
              <option value="sunday">Sunday</option>
              <option value="monday">Monday</option>
            </select>
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Daily Rewrite Days</span>
            <input
              type="number"
              min={1}
              max={60}
              value={dailyRewriteDays}
              onChange={(event) => setDailyRewriteDays(event.target.value)}
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Windsor Account ID (optional)</span>
            <input
              value={windsorAccountId}
              onChange={(event) => setWindsorAccountId(event.target.value)}
              placeholder="A1MY3C51FMRZ3Z-CA"
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Amazon Ads Profile ID (optional)</span>
            <input
              value={amazonAdsProfileId}
              onChange={(event) => setAmazonAdsProfileId(event.target.value)}
              placeholder="1234567890"
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Amazon Ads Account ID (optional)</span>
            <input
              value={amazonAdsAccountId}
              onChange={(event) => setAmazonAdsAccountId(event.target.value)}
              placeholder="123-456-7890123456"
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>

          <label className="text-sm">
            <span className="mb-1 block font-semibold text-[#0f172a]">Backfill Start Date (optional)</span>
            <input
              type="date"
              value={backfillStartDate}
              onChange={(event) => setBackfillStartDate(event.target.value)}
              className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            />
          </label>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={() => void handleCreateProfile()}
            disabled={submitDisabled}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
          >
            {saving ? "Creating Profile..." : "Create Profile"}
          </button>
          <Link
            href="/reports/wbr"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to WBR
          </Link>
          {clients.length === 0 && !loading ? (
            <Link
              href="/command-center/clients"
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
            >
              Open Command Center Clients
            </Link>
          ) : null}
        </div>

        {errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}

        {successMessage ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {successMessage}
          </p>
        ) : null}
      </div>
    </main>
  );
}
