import { useState } from "react";
import type { ComposerSkuGroup, ComposerSkuVariant } from "@agency/lib/composer/types";

interface GroupCardProps {
  group: ComposerSkuGroup;
  variants: ComposerSkuVariant[];
  onUpdateName: (name: string) => void;
  onDelete: () => void;
  onUnassignVariant: (variantId: string) => void;
  canDelete: boolean;
}

export const GroupCard = ({
  group,
  variants,
  onUpdateName,
  onDelete,
  onUnassignVariant,
  canDelete,
}: GroupCardProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(group.name);

  const handleSaveName = () => {
    if (editName.trim() && editName.trim() !== group.name) {
      onUpdateName(editName.trim());
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSaveName();
    } else if (e.key === "Escape") {
      setEditName(group.name);
      setIsEditing(false);
    }
  };

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        {isEditing ? (
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={handleSaveName}
            onKeyDown={handleKeyDown}
            autoFocus
            className="flex-1 rounded border border-[#cbd5e1] px-2 py-1 text-sm font-semibold text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
          />
        ) : (
          <button
            onClick={() => setIsEditing(true)}
            className="text-left text-sm font-semibold text-[#0f172a] hover:text-[#0a6fd6]"
          >
            {group.name}
          </button>
        )}
        {canDelete && (
          <button
            onClick={onDelete}
            className="text-xs text-[#94a3b8] hover:text-[#ef4444]"
            title="Delete group"
          >
            Delete
          </button>
        )}
      </div>

      {group.description && (
        <p className="mt-1 text-xs text-[#64748b]">{group.description}</p>
      )}

      <div className="mt-3">
        {variants.length === 0 ? (
          <p className="text-xs italic text-[#94a3b8]">No SKUs assigned</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {variants.map((variant) => (
              <span
                key={variant.id}
                className="group inline-flex items-center gap-1 rounded-full bg-[#f1f5f9] px-2 py-0.5 text-xs text-[#475569]"
              >
                {variant.sku}
                <button
                  onClick={() => onUnassignVariant(variant.id)}
                  className="hidden text-[#94a3b8] hover:text-[#ef4444] group-hover:inline"
                  title="Remove from group"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
