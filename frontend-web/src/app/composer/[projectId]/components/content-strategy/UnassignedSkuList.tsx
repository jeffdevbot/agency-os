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
        Click a SKU to assign it to a group
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {variants.map((variant) => (
          <div key={variant.id} className="group relative">
            <span className="inline-block rounded-full bg-[#fef3c7] px-3 py-1 text-xs font-medium text-[#92400e]">
              {variant.sku}
            </span>
            {groups.length > 0 && (
              <div className="absolute left-0 top-full z-10 mt-1 hidden min-w-[120px] rounded-lg border border-[#e2e8f0] bg-white py-1 shadow-lg group-hover:block">
                {groups.map((group) => (
                  <button
                    key={group.id}
                    onClick={() => onAssign(variant.id, group.id)}
                    className="block w-full px-3 py-1 text-left text-xs text-[#475569] hover:bg-[#f1f5f9]"
                  >
                    {group.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
