"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { canAccessNgram2, collectAssignedClientIds, NGRAM2_TOOL_SLUG } from "@/lib/ngram2/accessRules";

type Role = { id: string; slug: string; name: string };

type Brand = {
  id: string;
  name: string;
  clickupSpaceId: string | null;
  clickupListId: string | null;
  productKeywords: string[];
  amazonMarketplaces: string[];
};

type Client = { id: string; name: string; status: string; brands: Brand[] };

type TeamMember = {
  id: string;
  email: string;
  displayName: string | null;
  fullName: string | null;
  isAdmin: boolean;
  allowedTools: string[];
  employmentStatus: string;
  benchStatus: string;
  clickupUserId: string | null;
  slackUserId: string | null;
};

type Assignment = {
  id: string;
  clientId: string;
  brandId: string | null;
  teamMemberId: string;
  roleId: string;
  assignedAt: string;
  assignedBy: string | null;
};

type BootstrapResponse = {
  roles: Role[];
  clients: Client[];
  teamMembers: TeamMember[];
  assignments: Assignment[];
};

type ApiError = { error: { code: string; message: string } };

const displayMember = (member: TeamMember) =>
  member.displayName ?? member.fullName ?? member.email;

const TOOL_OPTIONS = [
  {
    slug: NGRAM2_TOOL_SLUG,
    label: "N-Gram 2.0",
    description: "AI preview and workbook generation for assigned clients.",
  },
] as const;

export default function CommandCenterTeamMemberDetailPage() {
  const params = useParams();
  const rawTeamMemberId = params.teamMemberId;
  const teamMemberId = Array.isArray(rawTeamMemberId) ? rawTeamMemberId[0] : rawTeamMemberId;

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);
  const [draftAllowedTools, setDraftAllowedTools] = useState<string[]>([]);
  const [toolSaveMessage, setToolSaveMessage] = useState<string | null>(null);
  const [toolSaving, setToolSaving] = useState(false);

  useEffect(() => {
    if (!teamMemberId) return;

    fetch("/api/command-center/bootstrap", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as BootstrapResponse & Partial<ApiError>;
        if (!response.ok) {
          setBootstrap(null);
          setLoading(false);
          setErrorMessage(json.error?.message ?? "Unable to load team member");
          return;
        }
        setBootstrap(json);
        setLoading(false);
        setErrorMessage(null);
      })
      .catch(() => {
        setBootstrap(null);
        setLoading(false);
        setErrorMessage("Unable to load team member");
      });
  }, [teamMemberId]);

  const teamMember = bootstrap?.teamMembers.find((member) => member.id === teamMemberId) ?? null;

  useEffect(() => {
    setDraftAllowedTools(teamMember?.allowedTools ?? []);
  }, [teamMember?.allowedTools]);

  const rolesById = new Map((bootstrap?.roles ?? []).map((role) => [role.id, role]));

  const clientsById = new Map((bootstrap?.clients ?? []).map((client) => [client.id, client]));

  const brandsById = new Map<string, Brand & { clientId: string; clientName: string }>();
  for (const client of bootstrap?.clients ?? []) {
    for (const brand of client.brands ?? []) {
      brandsById.set(brand.id, { ...brand, clientId: client.id, clientName: client.name });
    }
  }

  const assignments = (bootstrap?.assignments ?? [])
    .filter((assignment) => assignment.teamMemberId === teamMemberId && assignment.brandId !== null)
    .sort((a, b) => a.assignedAt.localeCompare(b.assignedAt));

  const assignedClientNames = useMemo(() => {
    const clientIds = collectAssignedClientIds(bootstrap?.assignments ?? [], teamMemberId ?? "");
    return clientIds
      .map((clientId) => clientsById.get(clientId)?.name ?? null)
      .filter((value): value is string => Boolean(value))
      .sort((left, right) => left.localeCompare(right));
  }, [bootstrap?.assignments, clientsById, teamMemberId]);

  const toolAccessDirty =
    teamMember !== null &&
    JSON.stringify([...draftAllowedTools].sort()) !== JSON.stringify([...teamMember.allowedTools].sort());

  const toggleToolAccess = (toolSlug: string) => {
    setToolSaveMessage(null);
    setDraftAllowedTools((current) =>
      current.includes(toolSlug)
        ? current.filter((entry) => entry !== toolSlug)
        : [...current, toolSlug].sort(),
    );
  };

  const saveToolAccess = async () => {
    if (!teamMemberId) return;

    setToolSaving(true);
    setToolSaveMessage(null);

    try {
      const response = await fetch(`/api/command-center/team/${teamMemberId}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ allowedTools: draftAllowedTools }),
      });
      const json = (await response.json()) as
        | { teamMember?: TeamMember }
        | { error?: { message?: string } };

      if (!response.ok || !("teamMember" in json) || !json.teamMember) {
        throw new Error(("error" in json && json.error?.message) || "Unable to save tool access");
      }

      setBootstrap((current) => {
        if (!current) return current;
        return {
          ...current,
          teamMembers: current.teamMembers.map((member) =>
            member.id === json.teamMember!.id ? json.teamMember! : member,
          ),
        };
      });
      setToolSaveMessage("Tool access saved.");
    } catch (error) {
      setToolSaveMessage(error instanceof Error ? error.message : "Unable to save tool access");
    } finally {
      setToolSaving(false);
    }
  };

  const groups = new Map<string, { title: string; rows: Assignment[] }>();
  for (const assignment of assignments) {
    const brandId = assignment.brandId;
    if (!brandId) continue;
    const brand = brandsById.get(brandId);
    const key = brand ? `brand:${brand.id}` : `brand:${brandId}`;
    const title = brand ? `${brand.clientName} → ${brand.name}` : `Brand ${brandId}`;
    const group = groups.get(key) ?? { title, rows: [] };
    group.rows.push(assignment);
    groups.set(key, group);
  }

  const grouped = Array.from(groups.values()).map((group) => ({
    title: group.title,
    rows: group.rows.sort((a, b) => {
      const roleA = rolesById.get(a.roleId)?.name ?? "";
      const roleB = rolesById.get(b.roleId)?.name ?? "";
      return roleA.localeCompare(roleB);
    }),
  }));

  if (loading) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm text-[#4c576f]">Loading…</p>
      </main>
    );
  }

  if (!teamMemberId) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-xl font-semibold text-[#0f172a]">Team member not found</h1>
        <p className="mt-4 text-sm text-[#4c576f]">teamMemberId is missing from the URL.</p>
      </main>
    );
  }

  if (!teamMember) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-xl font-semibold text-[#0f172a]">Team member not found</h1>
        {errorMessage ? (
          <p className="mt-4 text-sm text-[#991b1b]">{errorMessage}</p>
        ) : null}
        <div className="mt-6">
          <Link href="/command-center/team" className="text-sm font-semibold text-[#0a6fd6] hover:underline">
            Back to Team
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
            <h1 className="text-2xl font-semibold text-[#0f172a]">{displayMember(teamMember)}</h1>
            <p className="mt-2 text-sm text-[#4c576f]">
              {teamMember.email} • {teamMember.employmentStatus} • {teamMember.benchStatus}
              {teamMember.isAdmin ? " • admin" : ""}
            </p>
          </div>
          <Link
            href="/command-center/team"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to Team
          </Link>
        </div>

        {errorMessage ? (
          <p className="mt-6 rounded-2xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {errorMessage}
          </p>
        ) : null}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h2 className="text-lg font-semibold text-[#0f172a]">Assignments</h2>
        {assignments.length === 0 ? (
          <p className="mt-4 text-sm text-[#4c576f]">No assignments yet.</p>
        ) : (
          <div className="mt-6 space-y-6">
            {grouped.map((group) => (
              <div key={group.title} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="text-sm font-semibold text-[#0f172a]">{group.title}</div>
                <div className="mt-3 divide-y divide-slate-200">
                  {group.rows.map((row) => {
                    const roleName = rolesById.get(row.roleId)?.name ?? row.roleId;
                    const client = clientsById.get(row.clientId);
                    const clientHref = client ? `/command-center/clients/${client.id}` : null;
                    return (
                      <div key={row.id} className="flex flex-wrap items-center justify-between gap-4 py-3">
                        <div>
                          <div className="text-sm font-semibold text-[#0f172a]">{roleName}</div>
                        </div>
                        {clientHref ? (
                          <Link
                            href={clientHref}
                            className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
                          >
                            View Client
                          </Link>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-[#0f172a]">Tool Access</h2>
            <p className="mt-2 text-sm text-[#4c576f]">
              Feature access is managed here. Client and brand assignments still determine which data the tool can see.
            </p>
          </div>
          <button
            type="button"
            onClick={saveToolAccess}
            disabled={!toolAccessDirty || toolSaving}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-70"
          >
            {toolSaving ? "Saving…" : "Save Tool Access"}
          </button>
        </div>

        <div className="mt-6 space-y-3">
          {TOOL_OPTIONS.map((tool) => {
            const enabled = draftAllowedTools.includes(tool.slug);
            return (
              <label
                key={tool.slug}
                className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4"
              >
                <div>
                  <div className="text-sm font-semibold text-[#0f172a]">{tool.label}</div>
                  <p className="mt-1 text-sm text-[#4c576f]">{tool.description}</p>
                  {tool.slug === NGRAM2_TOOL_SLUG ? (
                    <p className="mt-2 text-xs text-[#64748b]">
                      {canAccessNgram2({
                        isAdmin: teamMember?.isAdmin ?? false,
                        allowedTools: draftAllowedTools,
                      })
                        ? assignedClientNames.length > 0
                          ? `Current client scope: ${assignedClientNames.join(", ")}.`
                          : "Enabled, but this teammate still needs at least one client or brand assignment to see data."
                        : "Disabled."}
                    </p>
                  ) : null}
                </div>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => toggleToolAccess(tool.slug)}
                  disabled={toolSaving}
                  className="mt-1 h-4 w-4"
                />
              </label>
            );
          })}
        </div>

        {toolSaveMessage ? (
          <p
            className={`mt-4 text-sm ${
              toolSaveMessage === "Tool access saved." ? "text-[#166534]" : "text-[#991b1b]"
            }`}
          >
            {toolSaveMessage}
          </p>
        ) : null}
      </div>
    </main>
  );
}
