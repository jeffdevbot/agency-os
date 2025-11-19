"use client";

import type { ComposerProject, ComposerSkuVariant, StrategyType } from "@agency/lib/composer/types";
import { useSkuGroups } from "@/lib/composer/hooks/useSkuGroups";
import { StrategyToggle } from "./StrategyToggle";
import { SkuGroupsBuilder } from "./SkuGroupsBuilder";

interface ContentStrategyStepProps {
  project: ComposerProject;
  variants: ComposerSkuVariant[];
  onSaveStrategy: (strategyType: StrategyType) => void;
  onVariantsChange: () => void;
}

export const ContentStrategyStep = ({
  project,
  variants,
  onSaveStrategy,
  onVariantsChange,
}: ContentStrategyStepProps) => {
  const {
    groups,
    isLoading: groupsLoading,
    error: groupsError,
    createGroup,
    updateGroup,
    deleteGroup,
    assignToGroup,
    unassignVariants,
  } = useSkuGroups(project.id);

  const handleStrategyChange = (strategy: StrategyType) => {
    onSaveStrategy(strategy);
  };

  const handleCreateGroup = async (name: string) => {
    await createGroup(name);
  };

  const handleUpdateGroup = async (groupId: string, name: string) => {
    await updateGroup(groupId, { name });
  };

  const handleDeleteGroup = async (groupId: string) => {
    await deleteGroup(groupId);
  };

  const handleAssignToGroup = async (groupId: string, variantIds: string[]) => {
    await assignToGroup(groupId, variantIds);
    onVariantsChange();
  };

  const handleUnassignVariants = async (variantIds: string[]) => {
    await unassignVariants(variantIds);
    onVariantsChange();
  };

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Content strategy
        </p>
        <p className="text-sm text-[#475569]">
          Choose how to generate content for your SKUs. This determines whether all SKUs
          share the same content or get unique content per group.
        </p>
      </div>

      <StrategyToggle
        value={project.strategyType}
        onChange={handleStrategyChange}
      />

      {project.strategyType === "distinct" && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-[#0f172a]">SKU Groups</h3>
            <p className="text-sm text-[#475569]">
              Create groups and assign SKUs to them. Each group will receive unique
              generated content.
            </p>
          </div>

          {groupsError && (
            <div className="rounded-lg bg-[#fef2f2] p-3 text-sm text-[#b91c1c]">
              {groupsError}
            </div>
          )}

          <SkuGroupsBuilder
            groups={groups}
            variants={variants}
            onCreateGroup={handleCreateGroup}
            onUpdateGroup={handleUpdateGroup}
            onDeleteGroup={handleDeleteGroup}
            onAssignToGroup={handleAssignToGroup}
            onUnassignVariants={handleUnassignVariants}
            isLoading={groupsLoading}
          />
        </div>
      )}

      {project.strategyType === "variations" && (
        <div className="rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4">
          <p className="text-sm text-[#64748b]">
            With the <strong>Variations</strong> strategy, all {variants.length} SKU
            {variants.length !== 1 ? "s" : ""} will share the same generated content.
            No grouping is needed.
          </p>
        </div>
      )}
    </div>
  );
};
