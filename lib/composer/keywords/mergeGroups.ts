import type {
  ComposerKeywordGroup,
  ComposerKeywordGroupOverride,
} from "@agency/lib/composer/types";

export interface MergedGroup {
  groupIndex: number;
  label: string | null;
  phrases: string[];
  metadata: Record<string, unknown>;
}

export const mergeGroupsWithOverrides = (
  aiGroups: ComposerKeywordGroup[],
  overrides: ComposerKeywordGroupOverride[],
): MergedGroup[] => {
  const groupsMap = new Map<number, MergedGroup>();

  aiGroups.forEach((group) => {
    groupsMap.set(group.groupIndex, {
      groupIndex: group.groupIndex,
      label: group.label,
      phrases: [...group.phrases],
      metadata: { ...group.metadata },
    });
  });

  const sortedOverrides = [...overrides].sort(
    (a, b) =>
      new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
  );

  sortedOverrides.forEach((override) => {
    const { action, phrase, targetGroupIndex, targetGroupLabel } = override;

    if (action === "remove") {
      for (const group of groupsMap.values()) {
        group.phrases = group.phrases.filter(
          (p) => p.toLowerCase() !== phrase.toLowerCase(),
        );
      }
      return;
    }

    if (action === "move") {
      for (const group of groupsMap.values()) {
        group.phrases = group.phrases.filter(
          (p) => p.toLowerCase() !== phrase.toLowerCase(),
        );
      }

      if (targetGroupIndex !== null && targetGroupIndex !== undefined) {
        const targetGroup = groupsMap.get(targetGroupIndex);
        if (targetGroup) {
          if (!targetGroup.phrases.some((p) => p.toLowerCase() === phrase.toLowerCase())) {
            targetGroup.phrases.push(phrase);
          }
        } else {
          groupsMap.set(targetGroupIndex, {
            groupIndex: targetGroupIndex,
            label: targetGroupLabel || `Group ${targetGroupIndex + 1}`,
            phrases: [phrase],
            metadata: { manuallyCreated: true },
          });
        }
      }
      return;
    }

    if (action === "add") {
      if (targetGroupIndex !== null && targetGroupIndex !== undefined) {
        const targetGroup = groupsMap.get(targetGroupIndex);
        if (targetGroup) {
          if (!targetGroup.phrases.some((p) => p.toLowerCase() === phrase.toLowerCase())) {
            targetGroup.phrases.push(phrase);
          }
        } else {
          groupsMap.set(targetGroupIndex, {
            groupIndex: targetGroupIndex,
            label: targetGroupLabel || `Group ${targetGroupIndex + 1}`,
            phrases: [phrase],
            metadata: { manuallyCreated: true },
          });
        }
      }
      return;
    }

    if (action === "rename") {
      if (targetGroupIndex === null || targetGroupIndex === undefined) return;
      const target = groupsMap.get(targetGroupIndex);
      if (target) {
        target.label = targetGroupLabel || target.label || `Group ${targetGroupIndex + 1}`;
      } else {
        groupsMap.set(targetGroupIndex, {
          groupIndex: targetGroupIndex,
          label: targetGroupLabel || `Group ${targetGroupIndex + 1}`,
          phrases: [],
          metadata: { manuallyCreated: true },
        });
      }
    }
  });

  const result = Array.from(groupsMap.values())
    .filter((group) => group.phrases.length > 0)
    .sort((a, b) => a.groupIndex - b.groupIndex);

  return result;
};
