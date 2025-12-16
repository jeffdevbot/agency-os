"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

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
  employmentStatus: string;
  benchStatus: string;
  allowedTools: string[];
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

export default function CommandCenterTeamMemberDetailPage() {
  const params = useParams();
  const rawTeamMemberId = params.teamMemberId;
  const teamMemberId = Array.isArray(rawTeamMemberId) ? rawTeamMemberId[0] : rawTeamMemberId;

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);

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
    </main>
  );
}
