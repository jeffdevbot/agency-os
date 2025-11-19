import { useState } from "react";
import type { ComposerSkuGroup, ComposerSkuVariant } from "@agency/lib/composer/types";
import { GroupCard } from "./GroupCard";
import { UnassignedSkuList } from "./UnassignedSkuList";

interface SkuGroupsBuilderProps {
  groups: ComposerSkuGroup[];
  variants: ComposerSkuVariant[];
  onCreateGroup: (name: string) => Promise<void>;
  onUpdateGroup: (groupId: string, name: string) => Promise<void>;
  onDeleteGroup: (groupId: string) => Promise<void>;
  onAssignToGroup: (groupId: string, variantIds: string[]) => Promise<void>;
  onUnassignVariants: (variantIds: string[]) => Promise<void>;
  isLoading?: boolean;
}

export const SkuGroupsBuilder = ({
  groups,
  variants,
  onCreateGroup,
  onUpdateGroup,
  onDeleteGroup,
  onAssignToGroup,
  onUnassignVariants,
  isLoading,
}: SkuGroupsBuilderProps) => {
  const [newGroupName, setNewGroupName] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Separate variants by assignment
  const unassignedVariants = variants.filter((v) => !v.groupId);
  const getGroupVariants = (groupId: string) =>
    variants.filter((v) => v.groupId === groupId);

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return;
    setIsCreating(true);
    try {
      await onCreateGroup(newGroupName.trim());
      setNewGroupName("");
    } finally {
      setIsCreating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleCreateGroup();
    }
  };

  const handleAssign = async (variantId: string, groupId: string) => {
    await onAssignToGroup(groupId, [variantId]);
  };

  const handleUnassign = async (variantId: string) => {
    await onUnassignVariants([variantId]);
  };

  if (isLoading) {
    return (
      <div className="py-8 text-center text-sm text-[#64748b]">
        Loading groups...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="block text-sm font-medium text-[#475569]">
            Create a group
          </label>
          <input
            type="text"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g., Red Variants, Pro Models"
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none"
            disabled={isCreating}
          />
        </div>
        <button
          onClick={handleCreateGroup}
          disabled={!newGroupName.trim() || isCreating}
          className="rounded-lg bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          Add
        </button>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-6 text-center">
          <p className="text-sm text-[#64748b]">
            No groups created yet. Create a group to start organizing your SKUs.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {groups.map((group) => (
            <GroupCard
              key={group.id}
              group={group}
              variants={getGroupVariants(group.id)}
              onUpdateName={(name) => onUpdateGroup(group.id, name)}
              onDelete={() => onDeleteGroup(group.id)}
              onUnassignVariant={handleUnassign}
              canDelete={getGroupVariants(group.id).length === 0}
            />
          ))}
        </div>
      )}

      <UnassignedSkuList
        variants={unassignedVariants}
        groups={groups}
        onAssign={handleAssign}
      />
    </div>
  );
};
