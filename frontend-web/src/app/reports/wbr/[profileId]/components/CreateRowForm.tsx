import type { WbrRow, WbrRowKind } from "../workspaceTypes";

type Props = {
  isCreatingRow: boolean;
  newRowLabel: string;
  newRowKind: WbrRowKind;
  newRowParentId: string;
  newRowSortOrder: string;
  activeParentRows: WbrRow[];
  onNewRowLabelChange: (value: string) => void;
  onNewRowKindChange: (value: WbrRowKind) => void;
  onNewRowParentIdChange: (value: string) => void;
  onNewRowSortOrderChange: (value: string) => void;
  onCreateRow: () => void;
};

export default function CreateRowForm({
  isCreatingRow,
  newRowLabel,
  newRowKind,
  newRowParentId,
  newRowSortOrder,
  activeParentRows,
  onNewRowLabelChange,
  onNewRowKindChange,
  onNewRowParentIdChange,
  onNewRowSortOrderChange,
  onCreateRow,
}: Props) {
  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm font-semibold text-[#0f172a]">Create Row</p>
      <div className="mt-3 grid gap-3 md:grid-cols-5">
        <label className="text-sm md:col-span-2">
          <span className="mb-1 block font-semibold text-[#0f172a]">Row Label</span>
          <input
            value={newRowLabel}
            onChange={(event) => onNewRowLabelChange(event.target.value)}
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
            placeholder="Accessories"
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Row Kind</span>
          <select
            value={newRowKind}
            onChange={(event) => onNewRowKindChange(event.target.value === "parent" ? "parent" : "leaf")}
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
          >
            <option value="leaf">leaf</option>
            <option value="parent">parent</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Parent Row</span>
          <select
            value={newRowParentId}
            onChange={(event) => onNewRowParentIdChange(event.target.value)}
            disabled={newRowKind === "parent"}
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-100"
          >
            <option value="">No parent</option>
            {activeParentRows.map((parent) => (
              <option key={parent.id} value={parent.id}>
                {parent.row_label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Sort Order</span>
          <input
            type="number"
            value={newRowSortOrder}
            onChange={(event) => onNewRowSortOrderChange(event.target.value)}
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
          />
        </label>
      </div>
      <div className="mt-3">
        <button
          onClick={onCreateRow}
          disabled={isCreatingRow}
          className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
        >
          {isCreatingRow ? "Creating..." : "Create Row"}
        </button>
      </div>
    </div>
  );
}
