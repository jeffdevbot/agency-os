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

const initialsFor = (value: string) => {
  const cleaned = value.trim();
  if (!cleaned) return "—";
  const parts = cleaned.split(/\s+/).slice(0, 2);
  return parts.map((p) => p.slice(0, 1).toUpperCase()).join("");
};

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

const toggle = (current: string[], value: string) =>
  current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value];

function MarketplaceMultiSelect(props: {
  value: string[];
  disabled?: boolean;
  onChange: (next: string[]) => void;
}) {
  const { value, onChange, disabled } = props;

  return (
    <div className="flex flex-wrap gap-2">
      {MARKETPLACE_OPTIONS.map((marketplace) => {
        const selected = value.includes(marketplace.code);
        return (
          <button
            key={marketplace.code}
            type="button"
            onClick={() => onChange(toggle(value, marketplace.code))}
            className={[
              "rounded-full px-3 py-1.5 text-xs font-semibold shadow-sm transition",
              selected
                ? "bg-[#0a6fd6] text-white shadow-[0_10px_20px_rgba(10,111,214,0.35)] hover:bg-[#0959ab]"
                : "bg-[#f1f5ff] text-[#0f172a] hover:bg-[#e7efff]",
              disabled ? "cursor-not-allowed opacity-60 hover:bg-inherit" : "",
            ].join(" ")}
            aria-pressed={selected}
            disabled={disabled}
          >
            {marketplace.label}
          </button>
        );
      })}
    </div>
  );
}

function OrgNode(props: {
  roleLabel: string;
  assignedMember: TeamMember | null;
  activeMembers: TeamMember[];
  value: string;
  pending?: boolean;
  disabled?: boolean;
  onAssign: (teamMemberId: string) => void;
}) {
  const { roleLabel, assignedMember, activeMembers, value, onAssign, disabled, pending } = props;
  const assignedLabel = assignedMember ? displayMember(assignedMember) : "";
  const initials = assignedMember ? initialsFor(assignedLabel) : "—";

  return (
    <div className="relative z-10 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div className="truncate text-[11px] font-bold uppercase tracking-wide text-slate-400">{roleLabel}</div>
        {pending ? <div className="text-[11px] font-semibold text-slate-400">Saving…</div> : null}
      </div>

      <div className="mt-2 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8eefc] text-xs font-bold text-[#0f172a]">
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-[#0f172a]">
            {assignedMember ? assignedLabel : "Unassigned"}
          </div>
          {assignedMember ? (
            <Link
              href={`/command-center/team/${assignedMember.id}`}
              className="text-xs font-semibold text-[#0a6fd6] hover:underline"
            >
              View profile
            </Link>
          ) : (
            <div className="text-xs text-[#64748b]">Select below</div>
          )}
        </div>
      </div>

      <select
        className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onAssign(event.target.value)}
        disabled={disabled}
      >
        <option value="">Unassigned</option>
        {activeMembers.map((member) => (
          <option key={member.id} value={member.id}>
            {displayMember(member)}
          </option>
        ))}
      </select>
    </div>
  );
}

function BrandModal(props: {
  open: boolean;
  mode: "create" | "edit";
  saving: boolean;
  title: string;
  brandName: string;
  brandKeywords: string;
  marketplaces: string[];
  onClose: () => void;
  onChangeName: (value: string) => void;
  onChangeKeywords: (value: string) => void;
  onChangeMarketplaces: (value: string[]) => void;
  onSubmit: () => void;
}) {
  const {
    open,
    mode,
    saving,
    title,
    brandName,
    brandKeywords,
    marketplaces,
    onClose,
    onChangeName,
    onChangeKeywords,
    onChangeMarketplaces,
    onSubmit,
  } = props;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 py-8">
      <div className="w-full max-w-2xl rounded-3xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-[#0f172a]">{title}</h2>
            <p className="mt-1 text-sm text-[#4c576f]">
              {mode === "create" ? "Add a new brand under this client." : "Update brand details."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-2xl bg-white px-3 py-2 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
            disabled={saving}
          >
            Close
          </button>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Brand name</div>
            <input
              value={brandName}
              onChange={(event) => onChangeName(event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
              placeholder="e.g. Acme Widgets"
              disabled={saving}
            />
          </label>

          <label className="space-y-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Keywords</div>
            <input
              value={brandKeywords}
              onChange={(event) => onChangeKeywords(event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
              placeholder="comma-separated"
              disabled={saving}
            />
          </label>
        </div>

        <div className="mt-6">
          <div className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Marketplaces</div>
          <div className="mt-3">
            <MarketplaceMultiSelect value={marketplaces} onChange={onChangeMarketplaces} disabled={saving} />
          </div>
        </div>

        <div className="mt-8 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow transition hover:shadow-lg"
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-70"
            disabled={saving || brandName.trim().length === 0}
          >
            {saving ? "Saving…" : mode === "create" ? "Add Brand" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

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
  const [brandModalOpen, setBrandModalOpen] = useState(false);
  const [brandModalMode, setBrandModalMode] = useState<"create" | "edit">("create");
  const [assigningKeys, setAssigningKeys] = useState<string[]>([]);

  const isAssigning = useCallback((key: string) => assigningKeys.includes(key), [assigningKeys]);
  const setAssigning = useCallback((key: string, next: boolean) => {
    setAssigningKeys((current) => {
      const exists = current.includes(key);
      if (next) return exists ? current : [...current, key];
      if (!exists) return current;
      return current.filter((k) => k !== key);
    });
  }, []);

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
    setBrandModalMode("edit");
    setBrandModalOpen(true);
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
    setBrandModalOpen(false);
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
    setBrandModalOpen(false);
    await refresh();
  };

  const onAssignForBrand = async (brandId: string, roleId: string, teamMemberId: string) => {
    setErrorMessage(null);
    if (!clientId) return;
    const safeClientId = clientId;

    const optimisticId = `optimistic:${brandId}:${roleId}`;
    setBootstrap((current) => {
      if (!current) return current;
      const existing = current.assignments.find(
        (a) => a.clientId === safeClientId && a.brandId === brandId && a.roleId === roleId,
      );
      const nextAssignments = existing
        ? current.assignments.map((a) =>
            a.id === existing.id ? { ...a, teamMemberId } : a,
          )
        : [
            {
              id: optimisticId,
              clientId: safeClientId,
              brandId,
              teamMemberId,
              roleId,
            },
            ...current.assignments,
          ];

      return { ...current, assignments: nextAssignments };
    });

    const response = await fetch("/api/command-center/assignments/upsert", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ clientId: safeClientId, roleId, teamMemberId, brandId }),
    });

    const json = (await response.json()) as { assignment?: Assignment } & Partial<ApiError>;
    if (!response.ok || !json.assignment) {
      setErrorMessage(json.error?.message ?? "Unable to save assignment");
      await refresh();
      return;
    }

    setBootstrap((current) => {
      if (!current) return current;
      const upserted = json.assignment!;
      const withoutOptimistic = current.assignments.filter((a) => a.id !== optimisticId);
      const withoutScope = withoutOptimistic.filter(
        (a) =>
          !(
            a.clientId === upserted.clientId &&
            a.brandId === upserted.brandId &&
            a.roleId === upserted.roleId
          ),
      );
      return { ...current, assignments: [upserted, ...withoutScope] };
    });
  };

  const onRemoveAssignment = async (assignmentId: string) => {
    setErrorMessage(null);

    setBootstrap((current) => {
      if (!current) return current;
      return { ...current, assignments: current.assignments.filter((a) => a.id !== assignmentId) };
    });

    if (assignmentId.startsWith("optimistic:")) {
      return;
    }

    const response = await fetch("/api/command-center/assignments/remove", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ assignmentId }),
    });

    const json = (await response.json()) as Partial<ApiError>;
    if (!response.ok) {
      setErrorMessage(json.error?.message ?? "Unable to remove assignment");
      await refresh();
      return;
    }
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

      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4 rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <div>
            <h2 className="text-lg font-semibold text-[#0f172a]">Brands</h2>
            <p className="mt-2 text-sm text-[#4c576f]">Manage brand details and assign org-chart roles.</p>
          </div>
          <button
            onClick={() => {
              cancelBrandEdit();
              setNewBrandName("");
              setNewBrandKeywords("");
              setNewBrandMarketplaces([]);
              setBrandModalMode("create");
              setBrandModalOpen(true);
            }}
            className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab]"
            disabled={saving}
          >
            Add New Brand
          </button>
        </div>

        {client.brands.length === 0 ? (
          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
            <p className="text-sm text-[#4c576f]">No brands yet.</p>
          </div>
        ) : (
	          <div className="space-y-6">
	            {client.brands.map((brand) => {
	              const assignments = assignmentsForBrand(brand.id);
	              const assignmentByRoleId = new Map(assignments.map((assignment) => [assignment.roleId, assignment]));

	              const getSlot = (roleSlug: string) => {
	                const key = `${brand.id}:${roleSlug}`;
	                const role = roleBySlug.get(roleSlug) ?? null;
	                if (!role) {
	                  return {
	                    key,
	                    roleId: null as string | null,
	                    assignment: null as Assignment | null,
	                    member: null as TeamMember | null,
	                  };
	                }
	                const assignment = assignmentByRoleId.get(role.id) ?? null;
	                const member = assignment ? teamMemberById.get(assignment.teamMemberId) ?? null : null;
	                return { key, roleId: role.id, assignment, member };
	              };

              const strategy = getSlot("strategy_director");
              const brandManager = getSlot("brand_manager");
              const catalogStrategist = getSlot("catalog_strategist");
              const catalogSpecialist = getSlot("catalog_specialist");
              const reportSpecialist = getSlot("report_specialist");
              const ppcStrategist = getSlot("ppc_strategist");
              const ppcSpecialist = getSlot("ppc_specialist");

	              const assignHandler = async (slot: ReturnType<typeof getSlot>, teamMemberId: string) => {
	                if (!slot.roleId) return;
	                setAssigning(slot.key, true);
	                try {
	                  if (!teamMemberId) {
	                    if (slot.assignment) await onRemoveAssignment(slot.assignment.id);
	                    return;
	                  }
	                  await onAssignForBrand(brand.id, slot.roleId, teamMemberId);
	                } finally {
	                  setAssigning(slot.key, false);
	                }
	              };

              return (
                <div
                  key={brand.id}
                  className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="truncate text-xl font-semibold text-[#0f172a]">{brand.name}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#4c576f]">
                        <span className="rounded-full bg-[#f1f5ff] px-3 py-1">
                          Keywords: {brand.productKeywords.join(", ") || "—"}
                        </span>
                        <span className="rounded-full bg-[#f1f5ff] px-3 py-1">
                          Marketplaces: {brand.amazonMarketplaces?.join(", ") || "—"}
                        </span>
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
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="mt-8">
                    <div className="text-sm font-semibold text-[#0f172a]">Org Chart</div>
                    <p className="mt-1 text-xs text-[#4c576f]">
                      Solid lines are direct reports; dotted line is support.
                    </p>

	                    <div className="relative mt-6 flex flex-col items-center">
	                      <OrgNode
	                        roleLabel="Strategy Director"
	                        assignedMember={strategy.member}
	                        activeMembers={activeTeamMembers}
	                        value={strategy.assignment?.teamMemberId ?? ""}
	                        pending={isAssigning(strategy.key)}
	                        disabled={saving || isAssigning(strategy.key) || !strategy.roleId}
	                        onAssign={(value) => void assignHandler(strategy, value)}
	                      />
	                      <div className="h-6 border-l-2 border-slate-300" />
	                      <OrgNode
	                        roleLabel="Brand Manager"
	                        assignedMember={brandManager.member}
	                        activeMembers={activeTeamMembers}
	                        value={brandManager.assignment?.teamMemberId ?? ""}
	                        pending={isAssigning(brandManager.key)}
	                        disabled={saving || isAssigning(brandManager.key) || !brandManager.roleId}
	                        onAssign={(value) => void assignHandler(brandManager, value)}
	                      />

                      <div className="relative mt-6 w-full max-w-5xl">
                        <div className="mx-auto h-6 w-0 border-l-2 border-slate-300" />
                        <div className="mx-auto h-0 w-full border-t-2 border-slate-300" />

                        <div className="relative grid grid-cols-1 gap-6 pt-6 lg:grid-cols-3">
                          <div className="relative flex flex-col items-center">
                            <div className="absolute -top-6 left-1/2 h-6 w-0 -translate-x-1/2 border-l-2 border-slate-300" />
	                            <OrgNode
	                              roleLabel="Catalog Strategist"
	                              assignedMember={catalogStrategist.member}
	                              activeMembers={activeTeamMembers}
	                              value={catalogStrategist.assignment?.teamMemberId ?? ""}
	                              pending={isAssigning(catalogStrategist.key)}
	                              disabled={saving || isAssigning(catalogStrategist.key) || !catalogStrategist.roleId}
	                              onAssign={(value) => void assignHandler(catalogStrategist, value)}
	                            />
	                            <div className="h-6 border-l-2 border-slate-300" />
	                            <OrgNode
	                              roleLabel="Catalog Specialist"
	                              assignedMember={catalogSpecialist.member}
	                              activeMembers={activeTeamMembers}
	                              value={catalogSpecialist.assignment?.teamMemberId ?? ""}
	                              pending={isAssigning(catalogSpecialist.key)}
	                              disabled={saving || isAssigning(catalogSpecialist.key) || !catalogSpecialist.roleId}
	                              onAssign={(value) => void assignHandler(catalogSpecialist, value)}
	                            />
	                          </div>

	                          <div className="relative flex flex-col items-center">
	                            <div className="absolute -top-6 left-1/2 h-6 w-0 -translate-x-1/2 border-l-2 border-dashed border-slate-300" />
	                            <div className="pointer-events-none opacity-0">
	                              <OrgNode
	                                roleLabel="Spacer"
	                                assignedMember={null}
	                                activeMembers={activeTeamMembers}
	                                value=""
	                                disabled
	                                onAssign={() => {}}
	                              />
	                            </div>
	                            <div className="h-6 border-l-2 border-dashed border-slate-300" />
	                            <OrgNode
	                              roleLabel="Report Specialist"
	                              assignedMember={reportSpecialist.member}
	                              activeMembers={activeTeamMembers}
	                              value={reportSpecialist.assignment?.teamMemberId ?? ""}
	                              pending={isAssigning(reportSpecialist.key)}
	                              disabled={saving || isAssigning(reportSpecialist.key) || !reportSpecialist.roleId}
	                              onAssign={(value) => void assignHandler(reportSpecialist, value)}
	                            />
	                          </div>

                          <div className="relative flex flex-col items-center">
                            <div className="absolute -top-6 left-1/2 h-6 w-0 -translate-x-1/2 border-l-2 border-slate-300" />
	                            <OrgNode
	                              roleLabel="PPC Strategist"
	                              assignedMember={ppcStrategist.member}
	                              activeMembers={activeTeamMembers}
	                              value={ppcStrategist.assignment?.teamMemberId ?? ""}
	                              pending={isAssigning(ppcStrategist.key)}
	                              disabled={saving || isAssigning(ppcStrategist.key) || !ppcStrategist.roleId}
	                              onAssign={(value) => void assignHandler(ppcStrategist, value)}
	                            />
	                            <div className="h-6 border-l-2 border-slate-300" />
	                            <OrgNode
	                              roleLabel="PPC Specialist"
	                              assignedMember={ppcSpecialist.member}
	                              activeMembers={activeTeamMembers}
	                              value={ppcSpecialist.assignment?.teamMemberId ?? ""}
	                              pending={isAssigning(ppcSpecialist.key)}
	                              disabled={saving || isAssigning(ppcSpecialist.key) || !ppcSpecialist.roleId}
	                              onAssign={(value) => void assignHandler(ppcSpecialist, value)}
	                            />
	                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <BrandModal
        open={brandModalOpen}
        mode={brandModalMode}
        saving={saving}
        title={brandModalMode === "create" ? "Add New Brand" : "Edit Brand"}
        brandName={brandModalMode === "create" ? newBrandName : editBrandName}
        brandKeywords={brandModalMode === "create" ? newBrandKeywords : editBrandKeywords}
        marketplaces={brandModalMode === "create" ? newBrandMarketplaces : editBrandMarketplaces}
        onClose={() => {
          setBrandModalOpen(false);
          if (brandModalMode === "create") {
            setNewBrandName("");
            setNewBrandKeywords("");
            setNewBrandMarketplaces([]);
          } else {
            cancelBrandEdit();
          }
        }}
        onChangeName={(value) => (brandModalMode === "create" ? setNewBrandName(value) : setEditBrandName(value))}
        onChangeKeywords={(value) =>
          brandModalMode === "create" ? setNewBrandKeywords(value) : setEditBrandKeywords(value)
        }
        onChangeMarketplaces={(value) =>
          brandModalMode === "create" ? setNewBrandMarketplaces(value) : setEditBrandMarketplaces(value)
        }
        onSubmit={() => {
          if (brandModalMode === "create") {
            onAddBrand();
          } else {
            onSaveBrandEdit();
          }
        }}
      />
    </main>
  );
}
