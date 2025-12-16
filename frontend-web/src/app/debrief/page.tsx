"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Meeting = {
  id: string;
  googleDocUrl: string;
  title: string;
  meetingDate: string | null;
  ownerEmail: string;
  status: string;
  createdAt: string;
  updatedAt: string;
};

type ApiError = { error: { code: string; message: string } };

export default function DebriefDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);

  const loadMeetings = useCallback(async () => {
    setErrorMessage(null);
    const response = await fetch("/api/debrief/meetings", { cache: "no-store" });
    const json = (await response.json()) as { meetings?: Meeting[] } & Partial<ApiError>;
    if (!response.ok) {
      setMeetings([]);
      setLoading(false);
      setErrorMessage(json.error?.message ?? "Unable to load meetings");
      return;
    }
    setMeetings(json.meetings ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetch("/api/debrief/meetings", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as { meetings?: Meeting[] } & Partial<ApiError>;
        if (!response.ok) {
          setMeetings([]);
          setLoading(false);
          setErrorMessage(json.error?.message ?? "Unable to load meetings");
          return;
        }
        setMeetings(json.meetings ?? []);
        setLoading(false);
      })
      .catch(() => {
        setMeetings([]);
        setLoading(false);
        setErrorMessage("Unable to load meetings");
      });
  }, []);

  const onSync = useCallback(async () => {
    setSyncing(true);
    setErrorMessage(null);
    const response = await fetch("/api/debrief/sync?limit=10", { method: "POST" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSyncing(false);
      setErrorMessage(json.error?.message ?? "Sync failed");
      return;
    }
    setSyncing(false);
    await loadMeetings();
  }, [loadMeetings]);

  return (
    <main className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a]">Debrief</h1>
            <p className="mt-2 text-sm text-[#4c576f]">Turn meeting notes into actionable tasks (ClickUp later).</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={loadMeetings}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              disabled={loading || syncing}
            >
              Refresh
            </button>
            <button
              onClick={onSync}
              className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
              disabled={syncing}
            >
              {syncing ? "Syncing…" : "Sync Notes"}
            </button>
          </div>
        </div>

        {errorMessage ? (
          <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Recent Meetings</h2>
        {loading ? (
          <p className="mt-4 text-sm text-[#4c576f]">Loading…</p>
        ) : meetings.length === 0 ? (
          <p className="mt-4 text-sm text-[#4c576f]">No meetings yet. Click “Sync Notes”.</p>
        ) : (
          <div className="mt-4 divide-y divide-slate-200">
            {meetings.map((meeting) => (
              <div key={meeting.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
                <div className="min-w-[240px]">
                  <div className="text-sm font-semibold text-[#0f172a]">{meeting.title}</div>
                  <div className="mt-1 text-xs text-[#4c576f]">
                    {meeting.ownerEmail} • {meeting.status}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <a
                    href={meeting.googleDocUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
                  >
                    Notes
                  </a>
                  <Link
                    href={`/debrief/meetings/${meeting.id}`}
                    className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
                  >
                    Review
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

