"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

type TeamMember = {
  id: string;
  authUserId: string | null;
  email: string;
  displayName: string | null;
  fullName: string | null;
  avatarUrl: string | null;
  isAdmin: boolean;
  role: string;
  allowedTools: string[];
  employmentStatus: string;
  benchStatus: string;
  clickupUserId: string | null;
  slackUserId: string | null;
  createdAt: string;
  updatedAt: string;
};

type ApiError = { error: { code: string; message: string } };

const TOOL_OPTIONS = [
  { slug: "ngram", label: "N-Gram" },
  { slug: "npat", label: "N-PAT" },
  { slug: "scribe", label: "Scribe" },
  { slug: "root-analysis", label: "Root Analysis" },
  { slug: "adscope", label: "AdScope" },
  { slug: "command-center", label: "Command Center" },
  { slug: "debrief", label: "Debrief" },
] as const;

const formatMembership = (member: TeamMember) =>
  member.authUserId ? "Linked" : "Ghost";

export default function CommandCenterTeamPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);

  const emailInputRef = useRef<HTMLInputElement | null>(null);
  const fullNameInputRef = useRef<HTMLInputElement | null>(null);

  const [createEmail, setCreateEmail] = useState("");
  const [createFullName, setCreateFullName] = useState("");
  const [createIsAdmin, setCreateIsAdmin] = useState(false);
  const [createAllowedTools, setCreateAllowedTools] = useState<string[]>([
    "command-center",
    "debrief",
  ]);

  const [editingId, setEditingId] = useState<string | null>(null);

  const [editDisplayName, setEditDisplayName] = useState("");
  const [editFullName, setEditFullName] = useState("");
  const [editClickupUserId, setEditClickupUserId] = useState("");
  const [editSlackUserId, setEditSlackUserId] = useState("");
  const [editIsAdmin, setEditIsAdmin] = useState(false);
  const [editEmploymentStatus, setEditEmploymentStatus] = useState("active");
  const [editAllowedTools, setEditAllowedTools] = useState<string[]>([]);

  const loadTeam = useCallback(async () => {
    setRefreshing(true);
    setErrorMessage(null);

    const response = await fetch("/api/command-center/team", { cache: "no-store" });
    const json = (await response.json()) as { teamMembers?: TeamMember[] } & Partial<ApiError>;

    if (!response.ok) {
      setTeamMembers([]);
      setLoading(false);
      setRefreshing(false);
      setErrorMessage(json.error?.message ?? "Unable to load team members");
      return;
    }

    setTeamMembers(json.teamMembers ?? []);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    fetch("/api/command-center/team", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as { teamMembers?: TeamMember[] } & Partial<ApiError>;

        if (!response.ok) {
          setTeamMembers([]);
          setLoading(false);
          setRefreshing(false);
          setErrorMessage(json.error?.message ?? "Unable to load team members");
          return;
        }

        setTeamMembers(json.teamMembers ?? []);
        setLoading(false);
        setRefreshing(false);
      })
      .catch(() => {
        setTeamMembers([]);
        setLoading(false);
        setRefreshing(false);
        setErrorMessage("Unable to load team members");
      });
  }, []);

  const toggleAllowedTool = useCallback((current: string[], slug: string) => {
    if (current.includes(slug)) return current.filter((value) => value !== slug);
    return [...current, slug];
  }, []);

  const beginEdit = useCallback((member: TeamMember) => {
    setEditingId(member.id);
    setEditDisplayName(member.displayName ?? "");
    setEditFullName(member.fullName ?? "");
    setEditClickupUserId(member.clickupUserId ?? "");
    setEditSlackUserId(member.slackUserId ?? "");
    setEditIsAdmin(member.isAdmin);
    setEditEmploymentStatus(member.employmentStatus);
    setEditAllowedTools(member.allowedTools ?? []);
  }, []);

  const onCreate = useCallback(async () => {
    setSaving(true);
    setErrorMessage(null);

    const email = (emailInputRef.current?.value ?? createEmail).trim();
    const fullName = (fullNameInputRef.current?.value ?? createFullName).trim();

    const response = await fetch("/api/command-center/team", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email,
        fullName,
        isAdmin: createIsAdmin,
        allowedTools: createAllowedTools,
      }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to create team member");
      return;
    }

    setCreateEmail("");
    setCreateFullName("");
    setCreateIsAdmin(false);
    setCreateAllowedTools(["command-center", "debrief"]);

    setSaving(false);
    await loadTeam();
  }, [createAllowedTools, createEmail, createFullName, createIsAdmin, loadTeam]);

  const onSaveEdit = useCallback(async () => {
    if (!editingId) return;
    setSaving(true);
    setErrorMessage(null);

    const response = await fetch(`/api/command-center/team/${editingId}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        displayName: editDisplayName,
        fullName: editFullName,
        clickupUserId: editClickupUserId,
        slackUserId: editSlackUserId,
        isAdmin: editIsAdmin,
        employmentStatus: editEmploymentStatus,
        allowedTools: editAllowedTools,
      }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to save changes");
      return;
    }

    setSaving(false);
    setEditingId(null);
    await loadTeam();
  }, [
    editAllowedTools,
    editClickupUserId,
    editDisplayName,
    editEmploymentStatus,
    editFullName,
    editIsAdmin,
    editSlackUserId,
    editingId,
    loadTeam,
  ]);

  const onArchive = useCallback(
    async (teamMemberId: string) => {
      setSaving(true);
      setErrorMessage(null);

      const response = await fetch(`/api/command-center/team/${teamMemberId}/archive`, {
        method: "POST",
      });
      const json = (await response.json()) as Partial<ApiError>;
      if (!response.ok) {
        setSaving(false);
        setErrorMessage(json.error?.message ?? "Unable to archive team member");
        return;
      }

      setSaving(false);
      setEditingId(null);
      await loadTeam();
    },
    [loadTeam],
  );

  const onDelete = useCallback(
    async (teamMemberId: string) => {
      const confirmed = window.confirm(
        "Delete this ghost profile permanently? This cannot be undone.",
      );
      if (!confirmed) return;

      setSaving(true);
      setErrorMessage(null);

      const response = await fetch(`/api/command-center/team/${teamMemberId}`, {
        method: "DELETE",
      });
      const json = (await response.json()) as Partial<ApiError>;
      if (!response.ok) {
        setSaving(false);
        setErrorMessage(json.error?.message ?? "Unable to delete team member");
        return;
      }

      setSaving(false);
      setEditingId(null);
      await loadTeam();
    },
    [loadTeam],
  );

  return (
    <main className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a]">Team</h1>
            <p className="mt-2 text-sm text-[#4c576f]">
              Create Ghost Profiles now; they&apos;ll merge into real logins on first Google sign-in.
            </p>
          </div>
          <button
            onClick={loadTeam}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
            disabled={loading || saving || refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {errorMessage ? (
          <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Add Team Member (Ghost)</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="space-y-1">
            <div className="text-sm font-semibold text-[#0f172a]">Email</div>
            <input
              name="email"
              type="email"
              autoComplete="email"
              ref={emailInputRef}
              value={createEmail}
              onChange={(event) => setCreateEmail(event.target.value)}
              onInput={(event) => setCreateEmail((event.target as HTMLInputElement).value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
              placeholder="name@ecomlabs.ca"
              disabled={saving}
            />
          </label>
          <label className="space-y-1">
            <div className="text-sm font-semibold text-[#0f172a]">Full Name</div>
            <input
              ref={fullNameInputRef}
              value={createFullName}
              onChange={(event) => setCreateFullName(event.target.value)}
              onInput={(event) => setCreateFullName((event.target as HTMLInputElement).value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
              placeholder="Optional"
              disabled={saving}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-[#0f172a]">
            <input
              type="checkbox"
              checked={createIsAdmin}
              onChange={(event) => setCreateIsAdmin(event.target.checked)}
              disabled={saving}
            />
            Admin
          </label>
        </div>

        <div className="mt-4">
          <div className="text-sm font-semibold text-[#0f172a]">Allowed Tools</div>
          <div className="mt-2 flex flex-wrap gap-3">
            {TOOL_OPTIONS.map((tool) => (
              <label key={tool.slug} className="flex items-center gap-2 rounded-2xl bg-[#f1f5ff] px-3 py-2 text-sm text-[#0f172a]">
                <input
                  type="checkbox"
                  checked={createAllowedTools.includes(tool.slug)}
                  onChange={() =>
                    setCreateAllowedTools((current) => toggleAllowedTool(current, tool.slug))
                  }
                  disabled={saving}
                />
                {tool.label}
              </label>
            ))}
          </div>
        </div>

        <div className="mt-6">
          <button
            onClick={onCreate}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
            disabled={saving || createEmail.trim().length === 0}
          >
            {saving ? "Saving…" : "Create Ghost Profile"}
          </button>
        </div>
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Roster</h2>
        {loading ? (
          <p className="mt-4 text-sm text-[#4c576f]">Loading…</p>
        ) : teamMembers.length === 0 ? (
          <p className="mt-4 text-sm text-[#4c576f]">No team members yet.</p>
        ) : (
          <div className="mt-4 divide-y divide-slate-200">
            {teamMembers.map((member) => (
              <div key={member.id} className="py-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
	                  <div className="min-w-[240px]">
	                    <Link
	                      href={`/command-center/team/${member.id}`}
	                      className="text-sm font-semibold text-[#0f172a] hover:underline"
	                    >
	                      {member.displayName ?? member.fullName ?? member.email}
	                    </Link>
	                    <div className="mt-1 text-xs text-[#4c576f]">
	                      {member.email} • {formatMembership(member)} • {member.employmentStatus} •{" "}
	                      {member.benchStatus}
	                      {member.isAdmin ? " • admin" : ""}
	                    </div>
	                  </div>
	                  <div className="flex flex-wrap items-center gap-2">
	                    <Link
	                      href={`/command-center/team/${member.id}`}
	                      className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
	                    >
	                      View
	                    </Link>
	                    <button
	                      onClick={() => beginEdit(member)}
	                      className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
	                      disabled={saving}
	                    >
	                      Edit
	                    </button>
	                    <button
	                      onClick={() => onArchive(member.id)}
	                      className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
	                      disabled={saving || member.employmentStatus === "inactive"}
	                    >
	                      Archive
	                    </button>
	                    {member.authUserId === null && member.employmentStatus === "inactive" ? (
	                      <button
	                        onClick={() => onDelete(member.id)}
	                        className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
	                        disabled={saving}
	                      >
	                        Delete
	                      </button>
	                    ) : null}
	                  </div>
	                </div>

                {editingId === member.id ? (
                  <div className="mt-4 rounded-2xl bg-[#f8fafc] p-4">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <label className="space-y-1">
                        <div className="text-sm font-semibold text-[#0f172a]">Display Name</div>
                        <input
                          value={editDisplayName}
                          onChange={(event) => setEditDisplayName(event.target.value)}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                          disabled={saving}
                        />
                      </label>
                      <label className="space-y-1">
                        <div className="text-sm font-semibold text-[#0f172a]">Full Name</div>
                        <input
                          value={editFullName}
                          onChange={(event) => setEditFullName(event.target.value)}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                          disabled={saving}
                        />
                      </label>
                      <label className="space-y-1">
                        <div className="text-sm font-semibold text-[#0f172a]">ClickUp User ID</div>
                        <input
                          value={editClickupUserId}
                          onChange={(event) => setEditClickupUserId(event.target.value)}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                          disabled={saving}
                        />
                      </label>
                      <label className="space-y-1">
                        <div className="text-sm font-semibold text-[#0f172a]">Slack User ID</div>
                        <input
                          value={editSlackUserId}
                          onChange={(event) => setEditSlackUserId(event.target.value)}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                          disabled={saving}
                        />
                      </label>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-4">
                      <label className="flex items-center gap-2 text-sm text-[#0f172a]">
                        <input
                          type="checkbox"
                          checked={editIsAdmin}
                          onChange={(event) => setEditIsAdmin(event.target.checked)}
                          disabled={saving}
                        />
                        Admin
                      </label>
                      <label className="flex items-center gap-2 text-sm text-[#0f172a]">
                        <span className="font-semibold">Employment</span>
                        <select
                          value={editEmploymentStatus}
                          onChange={(event) => setEditEmploymentStatus(event.target.value)}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                          disabled={saving}
                        >
                          <option value="active">active</option>
                          <option value="contractor">contractor</option>
                          <option value="inactive">inactive</option>
                        </select>
                      </label>
                    </div>

                    <div className="mt-4">
                      <div className="text-sm font-semibold text-[#0f172a]">Allowed Tools</div>
                      <div className="mt-2 flex flex-wrap gap-3">
                        {TOOL_OPTIONS.map((tool) => (
                          <label
                            key={tool.slug}
                            className="flex items-center gap-2 rounded-2xl bg-white px-3 py-2 text-sm text-[#0f172a]"
                          >
                            <input
                              type="checkbox"
                              checked={editAllowedTools.includes(tool.slug)}
                              onChange={() =>
                                setEditAllowedTools((current) =>
                                  toggleAllowedTool(current, tool.slug),
                                )
                              }
                              disabled={saving}
                            />
                            {tool.label}
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="mt-6 flex flex-wrap gap-3">
                      <button
                        onClick={onSaveEdit}
                        className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
                        disabled={saving}
                      >
                        {saving ? "Saving…" : "Save"}
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
                        disabled={saving}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
