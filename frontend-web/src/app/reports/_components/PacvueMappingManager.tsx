"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  PACVUE_GOAL_CODES,
  type PacvueCampaignMetrics,
  type PacvueGoalCode,
  type PacvueLeafRow,
  type PacvueMappingItem,
  deactivatePacvueMapping,
  listPacvueLeafRows,
  listPacvueMappings,
  listPacvueUnmapped,
  setPacvueExclusion,
  upsertPacvueManualMap,
} from "../wbr/_lib/pacvueMappingsApi";

type Props = {
  profileId: string | null;
  weeks?: number;
  onMutated?: () => void;
};

type Tab = "unmapped" | "mapped";

type EditorState = {
  campaignName: string;
  rowId: string;
  goalCode: PacvueGoalCode;
  initialRowId: string;
  initialGoalCode: PacvueGoalCode | "";
};

const formatCurrency = (value: string): string => {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return "$0.00";
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(parsed);
};

const formatNumber = (value: number): string =>
  new Intl.NumberFormat("en-CA").format(value);

const formatDate = (value: string | null): string => {
  if (!value) return "—";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(parsed);
};

const goalOptions: PacvueGoalCode[] = [...PACVUE_GOAL_CODES];

const isPacvueGoal = (value: string): value is PacvueGoalCode =>
  (goalOptions as readonly string[]).includes(value);

export default function PacvueMappingManager({ profileId, weeks = 4, onMutated }: Props) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [tab, setTab] = useState<Tab>("unmapped");
  const [expanded, setExpanded] = useState(false);
  const [search, setSearch] = useState("");
  const [unmapped, setUnmapped] = useState<PacvueCampaignMetrics[]>([]);
  const [mappings, setMappings] = useState<PacvueMappingItem[]>([]);
  const [leafRows, setLeafRows] = useState<PacvueLeafRow[]>([]);
  const [windowFrom, setWindowFrom] = useState<string | null>(null);
  const [windowTo, setWindowTo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditorState | null>(null);
  const [savingCampaign, setSavingCampaign] = useState<string | null>(null);

  const getToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Please sign in again.");
    return session.access_token;
  }, [supabase]);

  const reload = useCallback(async () => {
    if (!profileId) return;
    setLoading(true);
    setErrorMessage(null);
    try {
      const token = await getToken();
      const [unmappedRes, mappingsRes, leafRowsRes] = await Promise.all([
        listPacvueUnmapped(token, profileId, weeks),
        listPacvueMappings(token, profileId, weeks),
        listPacvueLeafRows(token, profileId),
      ]);
      setUnmapped(unmappedRes.items);
      setMappings(mappingsRes.items);
      setLeafRows(leafRowsRes);
      setWindowFrom(unmappedRes.date_from ?? mappingsRes.date_from);
      setWindowTo(unmappedRes.date_to ?? mappingsRes.date_to);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load mappings");
    } finally {
      setLoading(false);
    }
  }, [getToken, profileId, weeks]);

  useEffect(() => {
    if (!profileId || !expanded) return;
    void reload();
  }, [profileId, expanded, reload]);

  const filteredUnmapped = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return unmapped;
    return unmapped.filter((item) => item.campaign_name.toLowerCase().includes(needle));
  }, [search, unmapped]);

  const filteredMappings = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return mappings;
    return mappings.filter(
      (item) =>
        item.campaign_name.toLowerCase().includes(needle) ||
        (item.leaf_row_label ?? "").toLowerCase().includes(needle) ||
        (item.goal_code ?? "").toLowerCase().includes(needle)
    );
  }, [search, mappings]);

  const startEdit = (
    campaignName: string,
    initial?: { rowId?: string | null; goalCode?: string | null }
  ) => {
    const initialRowId = initial?.rowId ?? "";
    const rawGoal = initial?.goalCode ?? "";
    const initialGoal: PacvueGoalCode | "" = isPacvueGoal(rawGoal) ? rawGoal : "";
    const fallbackGoal: PacvueGoalCode = goalOptions[0];
    setEditing({
      campaignName,
      rowId: initialRowId,
      goalCode: initialGoal || fallbackGoal,
      initialRowId,
      initialGoalCode: initialGoal,
    });
  };

  const cancelEdit = () => setEditing(null);

  const handleSaveMapping = async () => {
    if (!profileId || !editing) return;
    if (!editing.rowId) {
      setErrorMessage("Pick a leaf row to map this campaign to.");
      return;
    }
    setSavingCampaign(editing.campaignName);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const token = await getToken();
      await upsertPacvueManualMap(token, profileId, {
        campaign_name: editing.campaignName,
        row_id: editing.rowId,
        goal_code: editing.goalCode,
      });
      setStatusMessage(`Mapped "${editing.campaignName}".`);
      setEditing(null);
      await reload();
      onMutated?.();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save mapping");
    } finally {
      setSavingCampaign(null);
    }
  };

  const handleExclude = async (campaignName: string) => {
    if (!profileId) return;
    if (!window.confirm(`Exclude "${campaignName}" from the WBR? You can clear this later from the mappings tab.`)) {
      return;
    }
    setSavingCampaign(campaignName);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const token = await getToken();
      await setPacvueExclusion(token, profileId, campaignName, true);
      setStatusMessage(`Excluded "${campaignName}".`);
      await reload();
      onMutated?.();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to exclude campaign");
    } finally {
      setSavingCampaign(null);
    }
  };

  const handleUnmap = async (campaignName: string) => {
    if (!profileId) return;
    if (!window.confirm(`Remove the mapping for "${campaignName}"?`)) return;
    setSavingCampaign(campaignName);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const token = await getToken();
      await deactivatePacvueMapping(token, profileId, campaignName);
      setStatusMessage(`Removed mapping for "${campaignName}".`);
      await reload();
      onMutated?.();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to remove mapping");
    } finally {
      setSavingCampaign(null);
    }
  };

  const windowLabel =
    windowFrom && windowTo
      ? `${formatDate(windowFrom)} – ${formatDate(windowTo)}`
      : `Last ${weeks} full weeks`;

  return (
    <div className="mt-4 rounded-2xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between gap-3 rounded-2xl px-5 py-4 text-left transition hover:bg-slate-50"
      >
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">
            Mapping Manager{" "}
            <span className="ml-2 text-xs font-medium text-[#64748b]">{windowLabel}</span>
          </p>
          <p className="mt-1 text-xs text-[#64748b]">
            Edit unmapped campaigns inline, exclude noise, or fix existing mappings. Admin-only — never shown in the client report.
          </p>
        </div>
        <span className="rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold text-[#0a6fd6]">
          {expanded ? "Collapse" : "Expand"}
        </span>
      </button>

      {expanded ? (
        <div className="border-t border-slate-200 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-2xl border border-slate-200 bg-slate-50 p-1 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setTab("unmapped")}
                className={
                  tab === "unmapped"
                    ? "rounded-xl bg-white px-3 py-1.5 text-[#92400e] shadow-sm"
                    : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
                }
              >
                Unmapped ({unmapped.length})
              </button>
              <button
                type="button"
                onClick={() => setTab("mapped")}
                className={
                  tab === "mapped"
                    ? "rounded-xl bg-white px-3 py-1.5 text-[#0f172a] shadow-sm"
                    : "rounded-xl px-3 py-1.5 text-[#475569] hover:text-[#0f172a]"
                }
              >
                All Mappings ({mappings.length})
              </button>
            </div>

            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={tab === "unmapped" ? "Filter unmapped..." : "Filter campaign / leaf / goal..."}
              className="flex-1 min-w-[220px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
            />

            <button
              type="button"
              onClick={() => void reload()}
              disabled={loading}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-[#0a6fd6] transition hover:-translate-y-0.5 hover:shadow disabled:cursor-not-allowed disabled:text-slate-400"
            >
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>

          {errorMessage ? (
            <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
              {errorMessage}
            </p>
          ) : null}
          {statusMessage ? (
            <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              {statusMessage}
            </p>
          ) : null}

          <div className="mt-4 overflow-x-auto">
            {tab === "unmapped" ? (
              <UnmappedTable
                items={filteredUnmapped}
                editing={editing}
                leafRows={leafRows}
                savingCampaign={savingCampaign}
                onStartEdit={(name) => startEdit(name)}
                onCancelEdit={cancelEdit}
                onChangeRow={(rowId) =>
                  setEditing((prev) => (prev ? { ...prev, rowId } : prev))
                }
                onChangeGoal={(goal) =>
                  setEditing((prev) => (prev ? { ...prev, goalCode: goal } : prev))
                }
                onSave={() => void handleSaveMapping()}
                onExclude={(name) => void handleExclude(name)}
              />
            ) : (
              <MappedTable
                items={filteredMappings}
                editing={editing}
                leafRows={leafRows}
                savingCampaign={savingCampaign}
                onStartEdit={(item) =>
                  startEdit(item.campaign_name, {
                    rowId: item.row_id,
                    goalCode: item.goal_code,
                  })
                }
                onCancelEdit={cancelEdit}
                onChangeRow={(rowId) =>
                  setEditing((prev) => (prev ? { ...prev, rowId } : prev))
                }
                onChangeGoal={(goal) =>
                  setEditing((prev) => (prev ? { ...prev, goalCode: goal } : prev))
                }
                onSave={() => void handleSaveMapping()}
                onUnmap={(name) => void handleUnmap(name)}
              />
            )}
          </div>

          {tab === "unmapped" && !loading && filteredUnmapped.length === 0 ? (
            <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              No unmapped campaigns in the current window.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

type UnmappedTableProps = {
  items: PacvueCampaignMetrics[];
  editing: EditorState | null;
  leafRows: PacvueLeafRow[];
  savingCampaign: string | null;
  onStartEdit: (campaignName: string) => void;
  onCancelEdit: () => void;
  onChangeRow: (rowId: string) => void;
  onChangeGoal: (goal: PacvueGoalCode) => void;
  onSave: () => void;
  onExclude: (campaignName: string) => void;
};

function UnmappedTable({
  items,
  editing,
  leafRows,
  savingCampaign,
  onStartEdit,
  onCancelEdit,
  onChangeRow,
  onChangeGoal,
  onSave,
  onExclude,
}: UnmappedTableProps) {
  return (
    <table className="min-w-full divide-y divide-slate-200 text-sm">
      <thead>
        <tr className="text-left text-xs font-semibold uppercase tracking-wide text-[#475569]">
          <th className="px-2 py-2">Campaign</th>
          <th className="px-2 py-2 text-right">Spend</th>
          <th className="px-2 py-2 text-right">Orders</th>
          <th className="px-2 py-2 text-right">Sales</th>
          <th className="px-2 py-2">Last Seen</th>
          <th className="px-2 py-2 text-right">Actions</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {items.map((item) => {
          const isEditing = editing?.campaignName === item.campaign_name;
          const isSaving = savingCampaign === item.campaign_name;
          return (
            <tr key={item.campaign_name} className="align-top">
              <td className="px-2 py-2 break-all text-[#0f172a]">
                <div className="font-medium">{item.campaign_name}</div>
                {isEditing ? (
                  <MappingEditor
                    leafRows={leafRows}
                    rowId={editing!.rowId}
                    goalCode={editing!.goalCode}
                    onChangeRow={onChangeRow}
                    onChangeGoal={onChangeGoal}
                    onSave={onSave}
                    onCancel={onCancelEdit}
                    saving={isSaving}
                  />
                ) : null}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                {formatCurrency(item.spend)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                {formatNumber(item.orders)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-[#475569]">
                {formatCurrency(item.sales)}
              </td>
              <td className="px-2 py-2 text-[#475569]">{formatDate(item.last_seen)}</td>
              <td className="px-2 py-2 text-right">
                <div className="inline-flex flex-wrap items-center justify-end gap-2">
                  {isEditing ? null : (
                    <button
                      type="button"
                      onClick={() => onStartEdit(item.campaign_name)}
                      disabled={isSaving}
                      className="rounded-lg border border-[#0a6fd6] bg-white px-2 py-1 text-xs font-semibold text-[#0a6fd6] hover:bg-[#0a6fd6] hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Map
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onExclude(item.campaign_name)}
                    disabled={isSaving}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-[#475569] hover:border-amber-300 hover:text-[#92400e] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Exclude
                  </button>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

type MappedTableProps = {
  items: PacvueMappingItem[];
  editing: EditorState | null;
  leafRows: PacvueLeafRow[];
  savingCampaign: string | null;
  onStartEdit: (item: PacvueMappingItem) => void;
  onCancelEdit: () => void;
  onChangeRow: (rowId: string) => void;
  onChangeGoal: (goal: PacvueGoalCode) => void;
  onSave: () => void;
  onUnmap: (campaignName: string) => void;
};

function MappedTable({
  items,
  editing,
  leafRows,
  savingCampaign,
  onStartEdit,
  onCancelEdit,
  onChangeRow,
  onChangeGoal,
  onSave,
  onUnmap,
}: MappedTableProps) {
  return (
    <table className="min-w-full divide-y divide-slate-200 text-sm">
      <thead>
        <tr className="text-left text-xs font-semibold uppercase tracking-wide text-[#475569]">
          <th className="px-2 py-2">Campaign</th>
          <th className="px-2 py-2">Leaf Row</th>
          <th className="px-2 py-2">Goal</th>
          <th className="px-2 py-2">Source</th>
          <th className="px-2 py-2 text-right">Spend</th>
          <th className="px-2 py-2 text-right">Orders</th>
          <th className="px-2 py-2 text-right">Actions</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {items.map((item) => {
          const isEditing = editing?.campaignName === item.campaign_name;
          const isSaving = savingCampaign === item.campaign_name;
          return (
            <tr key={`${item.campaign_name}:${item.id ?? "noid"}`} className="align-top">
              <td className="px-2 py-2 break-all text-[#0f172a]">
                <div className="font-medium">{item.campaign_name}</div>
                {isEditing ? (
                  <MappingEditor
                    leafRows={leafRows}
                    rowId={editing!.rowId}
                    goalCode={editing!.goalCode}
                    onChangeRow={onChangeRow}
                    onChangeGoal={onChangeGoal}
                    onSave={onSave}
                    onCancel={onCancelEdit}
                    saving={isSaving}
                  />
                ) : null}
              </td>
              <td className="px-2 py-2 text-[#0f172a]">{item.leaf_row_label ?? "—"}</td>
              <td className="px-2 py-2 text-[#0f172a]">{item.goal_code ?? "—"}</td>
              <td className="px-2 py-2 text-xs">
                {item.is_manual ? (
                  <span className="inline-flex rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 font-semibold text-violet-700">
                    Manual
                  </span>
                ) : (
                  <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 font-semibold text-slate-600">
                    Pacvue
                  </span>
                )}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                {formatCurrency(item.spend)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums text-[#0f172a]">
                {formatNumber(item.orders)}
              </td>
              <td className="px-2 py-2 text-right">
                <div className="inline-flex flex-wrap items-center justify-end gap-2">
                  {isEditing ? null : (
                    <button
                      type="button"
                      onClick={() => onStartEdit(item)}
                      disabled={isSaving}
                      className="rounded-lg border border-[#0a6fd6] bg-white px-2 py-1 text-xs font-semibold text-[#0a6fd6] hover:bg-[#0a6fd6] hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Edit
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onUnmap(item.campaign_name)}
                    disabled={isSaving}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-[#475569] hover:border-rose-300 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Unmap
                  </button>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

type EditorProps = {
  leafRows: PacvueLeafRow[];
  rowId: string;
  goalCode: PacvueGoalCode;
  onChangeRow: (rowId: string) => void;
  onChangeGoal: (goal: PacvueGoalCode) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
};

function MappingEditor({
  leafRows,
  rowId,
  goalCode,
  onChangeRow,
  onChangeGoal,
  onSave,
  onCancel,
  saving,
}: EditorProps) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2">
      <select
        value={rowId}
        onChange={(event) => onChangeRow(event.target.value)}
        className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
      >
        <option value="">Pick leaf row…</option>
        {leafRows.map((row) => (
          <option key={row.id} value={row.id}>
            {row.row_label ?? row.id}
          </option>
        ))}
      </select>
      <select
        value={goalCode}
        onChange={(event) => {
          const next = event.target.value;
          if (isPacvueGoal(next)) onChangeGoal(next);
        }}
        className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
      >
        {goalOptions.map((goal) => (
          <option key={goal} value={goal}>
            {goal}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={onSave}
        disabled={saving || !rowId}
        className="rounded-lg bg-[#0a6fd6] px-3 py-1 text-xs font-semibold text-white hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {saving ? "Saving..." : "Save"}
      </button>
      <button
        type="button"
        onClick={onCancel}
        disabled={saving}
        className="rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-[#475569] hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        Cancel
      </button>
    </div>
  );
}
