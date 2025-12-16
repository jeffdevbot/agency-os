"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

type Role = { id: string; slug: string; name: string };

type TeamMember = {
  id: string;
  email: string;
  displayName: string | null;
  fullName: string | null;
  isAdmin: boolean;
  employmentStatus: string;
};

type Assignment = {
  id: string;
  clientId: string;
  brandId: string | null;
  teamMemberId: string;
  roleId: string;
};

type Brand = {
  id: string;
  name: string;
  clickupSpaceId: string | null;
  clickupListId: string | null;
  productKeywords: string[];
  amazonMarketplaces: string[];
};

type Client = { id: string; name: string; status: string; brands: Brand[] };

type BootstrapResponse = {
  roles: Role[];
  clients: Client[];
  teamMembers: TeamMember[];
  assignments: Assignment[];
};

type ApiError = { error: { code: string; message: string } };

const displayMember = (member: TeamMember) =>
  member.displayName ?? member.fullName ?? member.email;

const MARKETPLACE_OPTIONS = [
  { code: "CA", label: "Canada" },
  { code: "US", label: "US" },
  { code: "MX", label: "Mexico" },
  { code: "BR", label: "Brazil" },
  { code: "UK", label: "UK" },
  { code: "FR", label: "France" },
  { code: "DE", label: "Germany" },
  { code: "NL", label: "Netherlands" },
  { code: "IT", label: "Italy" },
  { code: "ES", label: "Spain" },
  { code: "AU", label: "Australia" },
] as const;

const ORG_CHART_LAYOUT = {
  top: [
    { slug: "strategy_director", label: "Strategy Director" },
    { slug: "brand_manager", label: "Brand Manager" },
  ],
  catalog: [
    { slug: "catalog_strategist", label: "Catalog Strategist" },
    { slug: "catalog_specialist", label: "Catalog Specialist" },
  ],
  ppc: [
    { slug: "ppc_strategist", label: "PPC Strategist" },
    { slug: "ppc_specialist", label: "PPC Specialist" },
  ],
  report: [{ slug: "report_specialist", label: "Report Specialist" }],
} as const;

const toggle = (current: string[], value: string) =>
  current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value];

export default function CommandCenterClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawClientId = params.clientId;
  const clientId = Array.isArray(rawClientId) ? rawClientId[0] : rawClientId;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapResponse | null>(null);

  const [newBrandName, setNewBrandName] = useState("");
  const [newBrandKeywords, setNewBrandKeywords] = useState("");
  const [newBrandMarketplaces, setNewBrandMarketplaces] = useState<string[]>([]);

  const [editingBrandId, setEditingBrandId] = useState<string | null>(null);
  const [editBrandName, setEditBrandName] = useState("");
  const [editBrandKeywords, setEditBrandKeywords] = useState("");
  const [editBrandMarketplaces, setEditBrandMarketplaces] = useState<string[]>([]);

  useEffect(() => {
    if (!clientId) {
      return;
    }

    fetch("/api/command-center/bootstrap", { cache: "no-store" })
      .then(async (response) => {
        const json = (await response.json()) as BootstrapResponse & Partial<ApiError>;
        if (!response.ok) {
          setBootstrap(null);
          setLoading(false);
          setRefreshing(false);
          setErrorMessage(json.error?.message ?? "Unable to load client");
          return;
        }
        setBootstrap(json);
        setLoading(false);
        setRefreshing(false);
      })
      .catch(() => {
        setBootstrap(null);
        setLoading(false);
        setRefreshing(false);
        setErrorMessage("Unable to load client");
      });
  }, [clientId]);

  const client = useMemo(
    () => bootstrap?.clients.find((entry) => entry.id === clientId) ?? null,
    [bootstrap, clientId],
  );

  const assignmentsForBrand = useCallback(
    (brandId: string) =>
      (bootstrap?.assignments ?? []).filter((a) => a.clientId === clientId && a.brandId === brandId),
    [bootstrap?.assignments, clientId],
  );

  const activeTeamMembers = useMemo(
    () => (bootstrap?.teamMembers ?? []).filter((member) => member.employmentStatus !== "inactive"),
    [bootstrap?.teamMembers],
  );

  const roles = useMemo(() => bootstrap?.roles ?? [], [bootstrap?.roles]);

  const roleBySlug = useMemo(() => new Map(roles.map((role) => [role.slug, role])), [roles]);

  const teamMemberById = useMemo(
    () => new Map((bootstrap?.teamMembers ?? []).map((member) => [member.id, member])),
    [bootstrap?.teamMembers],
  );

  const refresh = async () => {
    setRefreshing(true);
    setErrorMessage(null);

    const response = await fetch("/api/command-center/bootstrap", { cache: "no-store" });
    const json = (await response.json()) as BootstrapResponse & Partial<ApiError>;
    if (!response.ok) {
      setBootstrap(null);
      setLoading(false);
      setRefreshing(false);
      setErrorMessage(json.error?.message ?? "Unable to load client");
      return;
    }

    setBootstrap(json);
    setLoading(false);
    setRefreshing(false);
  };

  const onArchiveClient = async () => {
    const confirmed = window.confirm("Archive this client?");
    if (!confirmed) return;

    setSaving(true);
    setErrorMessage(null);

    const response = await fetch(`/api/command-center/clients/${clientId}/archive`, {
      method: "POST",
    });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to archive client");
      return;
    }

    setSaving(false);
    await refresh();
  };

  const onDeleteClient = async () => {
    if (!client) return;

    const confirmed = window.confirm(
      client.status === "archived"
        ? "Delete this client permanently? This cannot be undone."
        : "Delete this client permanently? This will archive it first. This cannot be undone.",
    );
    if (!confirmed) return;

    setSaving(true);
    setErrorMessage(null);

    if (client.status !== "archived") {
      const archiveResponse = await fetch(`/api/command-center/clients/${clientId}/archive`, {
        method: "POST",
      });
      const archiveJson = (await archiveResponse.json()) as Partial<ApiError>;
      if (!archiveResponse.ok) {
        setSaving(false);
        setErrorMessage(archiveJson.error?.message ?? "Unable to archive client");
        return;
      }
    }

    const response = await fetch(`/api/command-center/clients/${clientId}`, { method: "DELETE" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to delete client");
      return;
    }

    setSaving(false);
    router.push("/command-center/clients");
  };

  const onDeleteBrand = async (brandId: string) => {
    const confirmed = window.confirm("Delete this brand permanently? This cannot be undone.");
    if (!confirmed) return;

    setSaving(true);
    setErrorMessage(null);

    const response = await fetch(`/api/command-center/brands/${brandId}`, { method: "DELETE" });
    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to delete brand");
      return;
    }

    setSaving(false);
    await refresh();
  };

  const beginBrandEdit = (brand: Brand) => {
    setEditingBrandId(brand.id);
    setEditBrandName(brand.name);
    setEditBrandKeywords((brand.productKeywords ?? []).join(", "));
    setEditBrandMarketplaces(brand.amazonMarketplaces ?? []);
  };

  const cancelBrandEdit = () => {
    setEditingBrandId(null);
    setEditBrandName("");
    setEditBrandKeywords("");
    setEditBrandMarketplaces([]);
  };

  const onSaveBrandEdit = async () => {
    if (!editingBrandId) return;

    setSaving(true);
    setErrorMessage(null);

    const keywords = editBrandKeywords
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k.length > 0);

    const response = await fetch(`/api/command-center/brands/${editingBrandId}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: editBrandName,
        productKeywords: keywords,
        amazonMarketplaces: editBrandMarketplaces,
      }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to update brand");
      return;
    }

    setSaving(false);
    cancelBrandEdit();
    await refresh();
  };

  const onAddBrand = async () => {
    setSaving(true);
    setErrorMessage(null);

    const keywords = newBrandKeywords
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k.length > 0);

    const response = await fetch(`/api/command-center/clients/${clientId}/brands`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: newBrandName,
        productKeywords: keywords,
        amazonMarketplaces: newBrandMarketplaces,
      }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to create brand");
      return;
    }

    setNewBrandName("");
    setNewBrandKeywords("");
    setNewBrandMarketplaces([]);
    setSaving(false);
    await refresh();
  };

  const onAssignForBrand = async (brandId: string, roleId: string, teamMemberId: string) => {
    setSaving(true);
    setErrorMessage(null);

    const response = await fetch("/api/command-center/assignments/upsert", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ clientId, roleId, teamMemberId, brandId }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to save assignment");
      return;
    }

    setSaving(false);
    await refresh();
  };

  const onRemoveAssignment = async (assignmentId: string) => {
    setSaving(true);
    setErrorMessage(null);

    const response = await fetch("/api/command-center/assignments/remove", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ assignmentId }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setSaving(false);
      setErrorMessage(json.error?.message ?? "Unable to remove assignment");
      return;
    }

    setSaving(false);
    await refresh();
  };

  if (loading) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm text-[#4c576f]">Loading…</p>
      </main>
    );
  }

  if (!clientId) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-xl font-semibold text-[#0f172a]">Client not found</h1>
        <p className="mt-4 text-sm text-[#4c576f]">clientId is missing from the URL.</p>
      </main>
    );
  }

  if (!client) {
    return (
      <main className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-xl font-semibold text-[#0f172a]">Client not found</h1>
        {errorMessage ? (
          <p className="mt-4 text-sm text-[#991b1b]">{errorMessage}</p>
        ) : null}
      </main>
    );
  }

  return (
    <main className="space-y-6">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-[#0f172a]">Client: {client.name}</h1>
            <p className="mt-2 text-sm text-[#4c576f]">
              Create brands under clients, then assign team members to brand roles.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={refresh}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              disabled={saving || refreshing}
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
            <button
              onClick={onArchiveClient}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#b91c1c] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              disabled={saving || client.status === "archived"}
            >
              Archive
            </button>
            <button
              onClick={onDeleteClient}
              className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#b91c1c] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
              disabled={saving}
            >
              Delete
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
        <h2 className="text-lg font-semibold text-[#0f172a]">Brands</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <input
            value={newBrandName}
            onChange={(event) => setNewBrandName(event.target.value)}
            className="min-w-[240px] flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
            placeholder="Brand name"
            disabled={saving}
          />
          <input
            value={newBrandKeywords}
            onChange={(event) => setNewBrandKeywords(event.target.value)}
            className="min-w-[280px] flex-[2] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
            placeholder="Keywords (comma-separated)"
            disabled={saving}
          />
          <button
            onClick={onAddBrand}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
            disabled={saving || newBrandName.trim().length === 0}
          >
            {saving ? "Saving…" : "Add Brand"}
          </button>
        </div>

        <div className="mt-4">
          <div className="text-sm font-semibold text-[#0f172a]">Marketplaces</div>
          <p className="mt-1 text-xs text-[#4c576f]">
            Used by Debrief routing. Stored as codes (CA, US, MX, BR, UK, FR, DE, NL, IT, ES, AU).
          </p>
          <div className="mt-2 flex flex-wrap gap-3">
            {MARKETPLACE_OPTIONS.map((marketplace) => (
              <label
                key={marketplace.code}
                className="flex items-center gap-2 rounded-2xl bg-[#f1f5ff] px-3 py-2 text-sm text-[#0f172a]"
              >
                <input
                  type="checkbox"
                  checked={newBrandMarketplaces.includes(marketplace.code)}
                  onChange={() =>
                    setNewBrandMarketplaces((current) => toggle(current, marketplace.code))
                  }
                  disabled={saving}
                />
                {marketplace.label}
              </label>
            ))}
          </div>
        </div>

        {client.brands.length === 0 ? (
          <p className="mt-6 text-sm text-[#4c576f]">No brands yet.</p>
        ) : (
          <div className="mt-6 space-y-6">
	            {client.brands.map((brand) => (
	              <div key={brand.id} className="rounded-2xl border border-slate-200 bg-white p-4">
	                <div className="flex flex-wrap items-start justify-between gap-4">
	                  {editingBrandId === brand.id ? (
	                    <div className="w-full space-y-4">
	                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
	                        <label className="space-y-1">
	                          <div className="text-sm font-semibold text-[#0f172a]">Brand name</div>
	                          <input
	                            value={editBrandName}
	                            onChange={(event) => setEditBrandName(event.target.value)}
	                            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
	                            disabled={saving}
	                          />
	                        </label>
	                        <label className="space-y-1">
	                          <div className="text-sm font-semibold text-[#0f172a]">Keywords</div>
	                          <input
	                            value={editBrandKeywords}
	                            onChange={(event) => setEditBrandKeywords(event.target.value)}
	                            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
	                            placeholder="comma-separated"
	                            disabled={saving}
	                          />
	                        </label>
	                      </div>

	                      <div>
	                        <div className="text-sm font-semibold text-[#0f172a]">Marketplaces</div>
	                        <div className="mt-2 flex flex-wrap gap-3">
	                          {MARKETPLACE_OPTIONS.map((marketplace) => (
	                            <label
	                              key={marketplace.code}
	                              className="flex items-center gap-2 rounded-2xl bg-[#f1f5ff] px-3 py-2 text-sm text-[#0f172a]"
	                            >
	                              <input
	                                type="checkbox"
	                                checked={editBrandMarketplaces.includes(marketplace.code)}
	                                onChange={() =>
	                                  setEditBrandMarketplaces((current) =>
	                                    toggle(current, marketplace.code),
	                                  )
	                                }
	                                disabled={saving}
	                              />
	                              {marketplace.label}
	                            </label>
	                          ))}
	                        </div>
	                      </div>

	                      <div className="flex flex-wrap items-center gap-2">
	                        <button
	                          onClick={onSaveBrandEdit}
	                          className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
	                          disabled={saving || editBrandName.trim().length === 0}
	                        >
	                          {saving ? "Saving…" : "Save"}
	                        </button>
	                        <button
	                          onClick={cancelBrandEdit}
	                          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
	                          disabled={saving}
	                        >
	                          Cancel
	                        </button>
	                      </div>
	                    </div>
	                  ) : (
	                    <>
	                      <div>
	                        <div className="text-sm font-semibold text-[#0f172a]">{brand.name}</div>
	                        <div className="mt-1 text-xs text-[#4c576f]">
	                          Keywords: {brand.productKeywords.join(", ") || "—"}
	                        </div>
	                        <div className="mt-1 text-xs text-[#4c576f]">
	                          Marketplaces: {brand.amazonMarketplaces?.join(", ") || "—"}
	                        </div>
	                      </div>
	                      <div className="flex flex-wrap items-center gap-2">
	                        <button
	                          onClick={() => beginBrandEdit(brand)}
	                          className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0a6fd6] shadow transition hover:shadow-lg"
	                          disabled={saving}
	                        >
	                          Edit
	                        </button>
	                        <button
	                          onClick={() => onDeleteBrand(brand.id)}
	                          className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
	                          disabled={saving}
	                        >
	                          Delete Brand
	                        </button>
	                      </div>
	                    </>
	                  )}
	                </div>

	                <div className="mt-6">
	                  <div className="text-sm font-semibold text-[#0f172a]">Org Chart</div>
                  <p className="mt-1 text-xs text-[#4c576f]">
                    Assign roles per brand. Each role slot accepts a single team member.
                  </p>

                  {(() => {
                    const assignments = assignmentsForBrand(brand.id);
                    const assignmentByRoleId = new Map(assignments.map((assignment) => [assignment.roleId, assignment]));

                    const renderSlot = (roleSlug: string, fallbackLabel: string) => {
                      const role = roleBySlug.get(roleSlug);
                      if (!role) return null;

                      const existing = assignmentByRoleId.get(role.id) ?? null;
                      const currentMember = existing ? teamMemberById.get(existing.teamMemberId) ?? null : null;

                      return (
                        <div
                          key={`${brand.id}:${roleSlug}`}
                          className="rounded-2xl border border-slate-200 bg-white px-4 py-3"
                        >
                          <div className="text-sm font-semibold text-[#0f172a]">{role.name || fallbackLabel}</div>
                          <div className="mt-1 text-xs text-[#4c576f]">
                            {currentMember ? (
                              <Link
                                href={`/command-center/team/${currentMember.id}`}
                                className="font-semibold text-[#0a6fd6] hover:underline"
                              >
                                {displayMember(currentMember)}
                              </Link>
                            ) : (
                              "Unassigned"
                            )}
                          </div>
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <select
                              className="min-w-[220px] flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                              value={existing?.teamMemberId ?? ""}
                              onChange={(event) => onAssignForBrand(brand.id, role.id, event.target.value)}
                              disabled={saving}
                            >
                              <option value="" disabled>
                                Select team member…
                              </option>
                              {activeTeamMembers.map((member) => (
                                <option key={member.id} value={member.id}>
                                  {displayMember(member)}
                                </option>
                              ))}
                            </select>
                            {existing ? (
                              <button
                                onClick={() => onRemoveAssignment(existing.id)}
                                className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#b91c1c] shadow transition hover:shadow-lg"
                                disabled={saving}
                              >
                                Remove
                              </button>
                            ) : null}
                          </div>
                        </div>
                      );
                    };

                    return (
                      <div className="mt-4 space-y-4">
                        <div className="grid gap-4 md:grid-cols-2">
                          {ORG_CHART_LAYOUT.top.map((slot) => renderSlot(slot.slug, slot.label))}
                        </div>

                        <div className="grid gap-4 lg:grid-cols-2">
                          <div className="rounded-2xl border border-slate-200 bg-[#f8fafc] p-4">
                            <div className="text-sm font-semibold text-[#0f172a]">Catalog</div>
                            <div className="mt-3 space-y-3">
                              {ORG_CHART_LAYOUT.catalog.map((slot) => renderSlot(slot.slug, slot.label))}
                            </div>
                          </div>
                          <div className="rounded-2xl border border-slate-200 bg-[#f8fafc] p-4">
                            <div className="text-sm font-semibold text-[#0f172a]">PPC</div>
                            <div className="mt-3 space-y-3">
                              {ORG_CHART_LAYOUT.ppc.map((slot) => renderSlot(slot.slug, slot.label))}
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                          {ORG_CHART_LAYOUT.report.map((slot) => renderSlot(slot.slug, slot.label))}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
