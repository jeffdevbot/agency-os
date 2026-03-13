"use client";

import type { WbrChildAsinItem } from "../../_lib/asinMappingApi";
import type { WbrRow } from "../../_lib/wbrApi";

type Props = {
  loading: boolean;
  refreshing: boolean;
  errorMessage: string | null;
  successMessage: string | null;
  childAsins: WbrChildAsinItem[];
  counts: {
    total: number;
    mapped: number;
    unmapped: number;
  };
  search: string;
  unmappedOnly: boolean;
  draftRowIds: Record<string, string>;
  savingRows: Record<string, boolean>;
  leafRows: WbrRow[];
  onSearchChange: (value: string) => void;
  onUnmappedOnlyChange: (value: boolean) => void;
  onDraftRowIdChange: (childAsin: string, rowId: string) => void;
  onSaveMapping: (item: WbrChildAsinItem) => void;
  onRefresh: () => void;
};

export default function AsinMappingCard({
  loading,
  refreshing,
  errorMessage,
  successMessage,
  childAsins,
  counts,
  search,
  unmappedOnly,
  draftRowIds,
  savingRows,
  leafRows,
  onSearchChange,
  onUnmappedOnlyChange,
  onDraftRowIdChange,
  onSaveMapping,
  onRefresh,
}: Props) {
  const activeLeafRows = leafRows.filter((row) => row.active);
  const leafRowById = Object.fromEntries(leafRows.map((row) => [row.id, row]));

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">ASIN Mapping</p>
          <p className="mt-1 text-sm text-[#4c576f]">
            Map each imported child ASIN to exactly one WBR leaf row. Parents remain rollups only.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading || refreshing}
          className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {refreshing ? "Refreshing..." : "Refresh ASINs"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Total</p>
          <p className="mt-2 text-2xl font-semibold text-[#0f172a]">{counts.total}</p>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Mapped</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-950">{counts.mapped}</p>
        </div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Unmapped</p>
          <p className="mt-2 text-2xl font-semibold text-amber-950">{counts.unmapped}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Search</span>
          <input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Search ASIN, SKU, title, or mapped row"
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
          />
        </label>
        <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-[#0f172a]">
          <input
            type="checkbox"
            checked={unmappedOnly}
            onChange={(event) => onUnmappedOnlyChange(event.target.checked)}
            className="h-4 w-4 rounded border-[#c7d8f5] text-[#0a6fd6] focus:ring-[#0a6fd6]"
          />
          Show unmapped only
        </label>
      </div>

      {errorMessage ? (
        <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {errorMessage}
        </p>
      ) : null}

      {successMessage ? (
        <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </p>
      ) : null}

      {leafRows.length === 0 ? (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Import or create leaf rows before mapping child ASINs.
        </p>
      ) : null}

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-[#f7faff]">
            <tr className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">
              <th className="px-3 py-2">Child ASIN</th>
              <th className="px-3 py-2">SKU</th>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Current Row</th>
              <th className="px-3 py-2">Map To Leaf</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-[#64748b]">
                  Loading child ASIN catalog...
                </td>
              </tr>
            ) : childAsins.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-[#64748b]">
                  No imported child ASINs yet.
                </td>
              </tr>
            ) : (
              childAsins.map((item) => {
                const selectedRowId = draftRowIds[item.child_asin] ?? "";
                const currentInactiveRow =
                  selectedRowId && leafRowById[selectedRowId] && leafRowById[selectedRowId].active === false
                    ? leafRowById[selectedRowId]
                    : null;

                return (
                  <tr key={item.child_asin} className="hover:bg-slate-50">
                    <td className="px-3 py-2 font-semibold text-[#0f172a]">{item.child_asin}</td>
                    <td className="px-3 py-2 text-[#4c576f]">{item.child_sku ?? "—"}</td>
                    <td className="px-3 py-2 text-[#0f172a]">{item.child_product_name ?? "—"}</td>
                    <td className="px-3 py-2 text-[#4c576f]">
                      {item.mapped_row_label ? (
                        <span className={item.mapped_row_active === false ? "text-amber-700" : undefined}>
                          {item.mapped_row_label}
                          {item.mapped_row_active === false ? " [inactive]" : ""}
                        </span>
                      ) : (
                        "Unmapped"
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <select
                        value={selectedRowId}
                        onChange={(event) => onDraftRowIdChange(item.child_asin, event.target.value)}
                        disabled={leafRows.length === 0}
                        className="w-full min-w-56 rounded-lg border border-[#c7d8f5] bg-[#f7faff] px-2 py-1 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-100"
                      >
                        <option value="">No row</option>
                        {activeLeafRows.map((row) => (
                          <option key={row.id} value={row.id}>
                            {row.row_label}
                          </option>
                        ))}
                        {currentInactiveRow ? (
                          <option value={currentInactiveRow.id} disabled>
                            [Inactive] {currentInactiveRow.row_label} (current)
                          </option>
                        ) : null}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => onSaveMapping(item)}
                        disabled={savingRows[item.child_asin] === true || leafRows.length === 0}
                        className="rounded-xl bg-white px-3 py-2 text-xs font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
                      >
                        {savingRows[item.child_asin] ? "Saving..." : "Save"}
                      </button>
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
