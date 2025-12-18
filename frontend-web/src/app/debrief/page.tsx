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
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [fetchedCount, setFetchedCount] = useState(0);

  const pageSize = 10;

  const loadMeetings = useCallback(async () => {
    setErrorMessage(null);
    setLoading(true);
    setLoadingMore(false);
    const url = new URL("/api/debrief/meetings", window.location.origin);
    url.searchParams.set("limit", String(pageSize));
    url.searchParams.set("offset", "0");
    const response = await fetch(url.toString(), { cache: "no-store" });
    const json = (await response.json()) as { meetings?: Meeting[] } & Partial<ApiError>;
    if (!response.ok) {
      setMeetings([]);
      setLoading(false);
      setErrorMessage(json.error?.message ?? "Unable to load meetings");
      return;
    }
    const next = json.meetings ?? [];
    setMeetings(next);
    setFetchedCount(next.length);
    setHasMore(next.length === pageSize);
    setLoading(false);
  }, []);

  useEffect(() => {
    const url = new URL("/api/debrief/meetings", window.location.origin);
    url.searchParams.set("limit", String(pageSize));
    url.searchParams.set("offset", "0");
    fetch(url.toString(), { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as { meetings?: Meeting[] } & Partial<ApiError>;
        if (!response.ok) {
          setMeetings([]);
          setLoading(false);
          setErrorMessage(json.error?.message ?? "Unable to load meetings");
          return;
        }
        const next = json.meetings ?? [];
        setMeetings(next);
        setFetchedCount(next.length);
        setHasMore(next.length === pageSize);
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

  const onRemoveMeeting = useCallback(
    async (meetingId: string) => {
      const confirmed = window.confirm("Remove this meeting from Debrief? (It will be marked dismissed.)");
      if (!confirmed) return;

      setRemovingId(meetingId);
      setErrorMessage(null);

      const response = await fetch(`/api/debrief/meetings/${meetingId}/dismiss`, { method: "POST" });
      const json = (await response.json()) as Partial<ApiError>;
      if (!response.ok) {
        setRemovingId(null);
        setErrorMessage(json.error?.message ?? "Remove failed");
        return;
      }

      setRemovingId(null);
      await loadMeetings();
    },
    [loadMeetings],
  );

  const onLoadMore = useCallback(async () => {
    if (loadingMore || loading || !hasMore) return;
    setLoadingMore(true);
    setErrorMessage(null);

    const url = new URL("/api/debrief/meetings", window.location.origin);
    url.searchParams.set("limit", String(pageSize));
    url.searchParams.set("offset", String(fetchedCount));
    const response = await fetch(url.toString(), { cache: "no-store" });
    const json = (await response.json()) as { meetings?: Meeting[] } & Partial<ApiError>;
    if (!response.ok) {
      setLoadingMore(false);
      setErrorMessage(json.error?.message ?? "Unable to load more meetings");
      return;
    }

    const next = json.meetings ?? [];
    setFetchedCount((current) => current + next.length);
    setMeetings((current) => {
      const seen = new Set(current.map((m) => m.id));
      const merged = [...current];
      for (const m of next) {
        if (!seen.has(m.id)) merged.push(m);
      }
      return merged;
    });
    setHasMore(next.length === pageSize);
    setLoadingMore(false);
  }, [fetchedCount, hasMore, loading, loadingMore]);

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
          <>
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
                    <button
                      onClick={() => void onRemoveMeeting(meeting.id)}
                      className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
                      disabled={removingId === meeting.id}
                    >
                      {removingId === meeting.id ? "Removing…" : "Remove"}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {hasMore ? (
              <div className="mt-6 flex justify-center">
                <button
                  onClick={() => void onLoadMore()}
                  className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:opacity-70"
                  disabled={loadingMore}
                >
                  {loadingMore ? "Loading…" : `Show ${pageSize} more`}
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}
