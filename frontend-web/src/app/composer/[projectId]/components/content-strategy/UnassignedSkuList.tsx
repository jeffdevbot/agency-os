import type { ComposerSkuVariant, ComposerSkuGroup } from "@agency/lib/composer/types";

interface UnassignedSkuListProps {
  variants: ComposerSkuVariant[];
  groups: ComposerSkuGroup[];
  onAssign: (variantId: string, groupId: string) => void;
}

export const UnassignedSkuList = ({
  variants,
  groups,
  onAssign,
}: UnassignedSkuListProps) => {
  if (variants.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-4 text-center">
        <p className="text-sm text-[#64748b]">All SKUs are assigned to groups</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white p-4">
      <h4 className="text-sm font-semibold text-[#0f172a]">Unassigned SKUs</h4>
      <p className="mt-1 text-xs text-[#64748b]">
        Choose a group for each SKU. Newly created groups appear instantly in the dropdown.
      </p>

      {groups.length === 0 ? (
        <div className="mt-3 rounded-lg border border-dashed border-[#cbd5e1] bg-[#fff8eb] px-4 py-3 text-sm text-[#92400e]">
          Create a group above to start assigning SKUs.
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-[#e2e8f0] text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-[#94a3b8]">
                <th className="py-2 pr-4">SKU</th>
                <th className="py-2 pr-4">ASIN</th>
                <th className="py-2">Assign to group</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f1f5f9]">
              {variants.map((variant) => (
                <tr key={variant.id} className="text-[#0f172a]">
                  <td className="py-3 pr-4 font-medium">{variant.sku}</td>
                  <td className="py-3 pr-4 text-[#475569]">{variant.asin ?? "—"}</td>
                  <td className="py-3">
                    <select
                      defaultValue=""
                      onChange={(event) => {
                        const value = event.target.value;
                        if (value) {
                          void onAssign(variant.id, value);
                        }
                      }}
                      className="w-full rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
                    >
                      <option value="" disabled>
                        Select a group…
                      </option>
                      {groups.map((group) => (
                        <option key={group.id} value={group.id}>
                          {group.name}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
