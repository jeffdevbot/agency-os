import type { RowEditState, WbrRow } from "../workspaceTypes";

type Props = {
  loading: boolean;
  parentRows: WbrRow[];
  rowEdits: Record<string, RowEditState>;
  savingRows: Record<string, boolean>;
  onRowLabelChange: (rowId: string, value: string) => void;
  onRowSortOrderChange: (rowId: string, value: string) => void;
  onRowActiveChange: (rowId: string, value: boolean) => void;
  onSaveRow: (row: WbrRow) => void;
  onDeactivateRow: (row: WbrRow) => void;
  onDeleteRowPermanently: (row: WbrRow) => void;
};

export default function ParentRowsTable({
  loading,
  parentRows,
  rowEdits,
  savingRows,
  onRowLabelChange,
  onRowSortOrderChange,
  onRowActiveChange,
  onSaveRow,
  onDeactivateRow,
  onDeleteRowPermanently,
}: Props) {
  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-sm font-semibold text-[#0f172a]">Parent Rows</p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2">Sort</th>
              <th className="px-3 py-2">Active</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {loading ? (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-[#64748b]">
                  Loading rows...
                </td>
              </tr>
            ) : parentRows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-[#64748b]">
                  No parent rows yet.
                </td>
              </tr>
            ) : (
              parentRows.map((row) => {
                const edit = rowEdits[row.id];
                if (!edit) return null;
                return (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <input
                        value={edit.row_label}
                        onChange={(event) => onRowLabelChange(row.id, event.target.value)}
                        className="w-full rounded-lg border border-[#c7d8f5] bg-[#f7faff] px-2 py-1 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        value={edit.sort_order}
                        onChange={(event) => onRowSortOrderChange(row.id, event.target.value)}
                        className="w-24 rounded-lg border border-[#c7d8f5] bg-[#f7faff] px-2 py-1 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={edit.active}
                        onChange={(event) => onRowActiveChange(row.id, event.target.checked)}
                        className="h-4 w-4 rounded border-[#c7d8f5] text-[#0a6fd6] focus:ring-[#0a6fd6]"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => onSaveRow(row)}
                          disabled={savingRows[row.id] === true}
                          className="rounded-xl bg-white px-3 py-2 text-xs font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
                        >
                          {savingRows[row.id] ? "Saving..." : "Save"}
                        </button>
                        {row.active ? (
                          <button
                            onClick={() => onDeactivateRow(row)}
                            disabled={savingRows[row.id] === true}
                            className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            Deactivate
                          </button>
                        ) : null}
                        <button
                          onClick={() => onDeleteRowPermanently(row)}
                          disabled={savingRows[row.id] === true}
                          className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-800 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Delete Permanently
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
