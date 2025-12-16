"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

type Meeting = {
  id: string;
  googleDocUrl: string;
  title: string;
  meetingDate: string | null;
  ownerEmail: string;
  status: string;
  rawContent: string | null;
  summaryContent: string | null;
  extractionError: string | null;
  createdAt: string;
  updatedAt: string;
};

type Task = {
  id: string;
  meetingNoteId: string;
  rawText: string;
  title: string;
  description: string | null;
  suggestedBrandId: string | null;
  suggestedAssigneeId: string | null;
  taskType: string | null;
  status: string;
  clickupTaskId: string | null;
  clickupError: string | null;
  createdAt: string;
  updatedAt: string;
};

type ApiError = { error: { code: string; message: string } };

export default function DebriefMeetingPage() {
  const params = useParams();
  const rawMeetingId = params.meetingId;
  const meetingId = Array.isArray(rawMeetingId) ? rawMeetingId[0] : rawMeetingId;

  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [sendingAll, setSendingAll] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState<string>("");
  const [draftDescription, setDraftDescription] = useState<string>("");

  const reloadMeeting = async () => {
    if (!meetingId) return;
    const response = await fetch(`/api/debrief/meetings/${meetingId}`, { cache: "no-store" });
    const json = (await response.json()) as { meeting?: Meeting; tasks?: Task[] } & Partial<ApiError>;
    if (!response.ok) {
      setMeeting(null);
      setTasks([]);
      setLoading(false);
      setErrorMessage(json.error?.message ?? "Unable to load meeting");
      return;
    }
    setMeeting(json.meeting ?? null);
    setTasks(json.tasks ?? []);
    setLoading(false);
    setErrorMessage(null);
  };

  useEffect(() => {
    void reloadMeeting();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meetingId]);

  const onExtract = async () => {
    if (!meetingId) return;
    setExtracting(true);
    setErrorMessage(null);

    const response = await fetch(`/api/debrief/meetings/${meetingId}/extract`, { method: "POST" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setExtracting(false);
      setErrorMessage(json.error?.message ?? "Extraction failed");
      return;
    }
    await reloadMeeting();
    setExtracting(false);
  };

  const onSendAll = async () => {
    if (!meetingId) return;
    setSendingAll(true);
    setErrorMessage(null);

    const response = await fetch(`/api/debrief/meetings/${meetingId}/send-to-clickup`, { method: "POST" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSendingAll(false);
      setErrorMessage(json.error?.message ?? "Send all failed");
      return;
    }
    await reloadMeeting();
    setSendingAll(false);
  };

  const onRemoveTask = async (taskId: string) => {
    setErrorMessage(null);
    const response = await fetch(`/api/debrief/tasks/${taskId}`, { method: "DELETE" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setErrorMessage(json.error?.message ?? "Remove failed");
      return;
    }
    await reloadMeeting();
  };

  const onSendTask = async (taskId: string) => {
    setErrorMessage(null);
    const response = await fetch(`/api/debrief/tasks/${taskId}/send-to-clickup`, { method: "POST" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setErrorMessage(json.error?.message ?? "Send failed");
      return;
    }
    await reloadMeeting();
  };

  const onStartEdit = (task: Task) => {
    setEditingTaskId(task.id);
    setDraftTitle(task.title);
    setDraftDescription(task.description ?? "");
  };

  const onCancelEdit = () => {
    setEditingTaskId(null);
    setDraftTitle("");
    setDraftDescription("");
  };

  const onSaveEdit = async (taskId: string) => {
    setErrorMessage(null);
    const response = await fetch(`/api/debrief/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: draftTitle, description: draftDescription }),
    });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setErrorMessage(json.error?.message ?? "Save failed");
      return;
    }
    setEditingTaskId(null);
    await reloadMeeting();
  };

  if (loading) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm text-[#4c576f]">Loading…</p>
      </main>
    );
  }

  if (!meetingId) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-xl font-semibold text-[#0f172a]">Meeting not found</h1>
        <p className="mt-4 text-sm text-[#4c576f]">meetingId is missing from the URL.</p>
      </main>
    );
  }

  if (!meeting) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-xl font-semibold text-[#0f172a]">Meeting not found</h1>
        {errorMessage ? <p className="mt-4 text-sm text-[#991b1b]">{errorMessage}</p> : null}
        <div className="mt-6">
          <Link href="/debrief" className="text-sm font-semibold text-[#0a6fd6] hover:underline">
            Back to Debrief
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a]">{meeting.title}</h1>
            <p className="mt-2 text-sm text-[#4c576f]">
              {meeting.ownerEmail} • {meeting.status}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={meeting.googleDocUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
            >
              View Notes
            </a>
            <button
              onClick={onExtract}
              className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
              disabled={extracting || meeting.status === "processing"}
            >
              {extracting ? "Extracting…" : "Extract Tasks"}
            </button>
            <button
              onClick={onSendAll}
              className="rounded-2xl bg-[#0f172a] px-4 py-3 text-sm font-semibold text-white shadow transition hover:bg-[#0b1220]"
              disabled={sendingAll || meeting.status === "processing" || tasks.length === 0}
            >
              {sendingAll ? "Sending…" : "Send All to ClickUp"}
            </button>
            <Link
              href="/debrief"
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
            >
              Back
            </Link>
          </div>
        </div>

        {errorMessage ? (
          <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Extracted Tasks</h2>
        <p className="mt-2 text-sm text-[#4c576f]">
          Remove non-ClickUp tasks, edit the rest, then send to ClickUp (individually or all at once).
        </p>
        {tasks.length === 0 ? (
          <p className="mt-4 text-sm text-[#4c576f]">No tasks yet.</p>
        ) : (
          <div className="mt-6 space-y-4">
            {tasks.map((task) => (
              <div key={task.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-[240px] flex-1">
                    {editingTaskId === task.id ? (
                      <div className="space-y-2">
                        <input
                          value={draftTitle}
                          onChange={(e) => setDraftTitle(e.target.value)}
                          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#0f172a]"
                        />
                        <textarea
                          value={draftDescription}
                          onChange={(e) => setDraftDescription(e.target.value)}
                          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#0f172a]"
                          rows={3}
                        />
                      </div>
                    ) : (
                      <>
                        <div className="text-sm font-semibold text-[#0f172a]">{task.title}</div>
                        <div className="mt-1 text-xs text-[#4c576f]">
                          {task.clickupTaskId
                            ? `Sent to ClickUp • ${task.clickupTaskId}`
                            : task.clickupError
                              ? "Send failed"
                              : "Draft"}
                        </div>
                        {task.description ? <p className="mt-3 text-sm text-[#0f172a]">{task.description}</p> : null}
                        {task.clickupError ? (
                          <p className="mt-3 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-3 py-2 text-xs text-[#991b1b]">
                            ClickUp error: {task.clickupError}
                          </p>
                        ) : null}
                      </>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {editingTaskId === task.id ? (
                      <>
                        <button
                          onClick={() => onSaveEdit(task.id)}
                          className="rounded-2xl bg-[#0a6fd6] px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-[#0959ab]"
                        >
                          Save
                        </button>
                        <button
                          onClick={onCancelEdit}
                          className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => onStartEdit(task)}
                          className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => onSendTask(task.id)}
                          className="rounded-2xl bg-[#0f172a] px-3 py-2 text-sm font-semibold text-white shadow transition hover:bg-[#0b1220]"
                          disabled={Boolean(task.clickupTaskId)}
                        >
                          {task.clickupTaskId ? "Sent" : "Send to ClickUp"}
                        </button>
                        <button
                          onClick={() => onRemoveTask(task.id)}
                          className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#991b1b] shadow transition hover:shadow-lg"
                        >
                          Remove Task
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Raw Notes</h2>
        {meeting.rawContent ? (
          <pre className="mt-4 max-h-[520px] overflow-auto whitespace-pre-wrap rounded-2xl bg-[#0b1220] p-4 text-xs text-[#e2e8f0]">
            {meeting.rawContent}
          </pre>
        ) : (
          <p className="mt-4 text-sm text-[#4c576f]">No raw content stored for this file type yet.</p>
        )}
      </div>
    </main>
  );
}
