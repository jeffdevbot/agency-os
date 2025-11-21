'use client';

import { useState, useEffect } from 'react';
import { DndContext, DragEndEvent, closestCenter } from '@dnd-kit/core';
import type { ComposerKeywordPool } from '@agency/lib/composer/types';
import { useKeywordPools } from '@/lib/composer/hooks/useKeywordPools';
import type { KeywordGroup, GroupingConfig } from './types';
import { KeywordGroupCard } from './KeywordGroupCard';
import { GroupingConfigForm } from './GroupingConfigForm';

interface GroupingPlanStepProps {
  projectId: string;
  pools: ComposerKeywordPool[];
  onContinue?: () => void;
}

export function GroupingPlanStep({ projectId, pools, onContinue }: GroupingPlanStepProps) {
  const [activeTab, setActiveTab] = useState<'body' | 'titles'>('body');
  const [groups, setGroups] = useState<KeywordGroup[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showConfig, setShowConfig] = useState(true);

  const {
    generateGroupingPlan,
    getGroups,
    addOverride,
    resetOverrides,
    approveGrouping,
    unapproveGrouping,
  } = useKeywordPools(projectId);

  const currentPool = pools.find((p) => p.poolType === activeTab);
  const isApproved = currentPool?.status === 'grouped';
  const canApprove =
    currentPool?.status === 'cleaned' && groups.length > 0 && groups.every((g) => g.phrases.length > 0);

  useEffect(() => {
    if (currentPool) {
      loadGroups(currentPool.id);
    }
  }, [currentPool?.id]);

  const loadGroups = async (poolId: string) => {
    const result = await getGroups(poolId);
    if (result) {
      setGroups(result.groups);
    }
  };

  const handleGenerate = async (config: GroupingConfig) => {
    if (!currentPool) return;

    setIsGenerating(true);
    try {
      await generateGroupingPlan(currentPool.id, config);
      await loadGroups(currentPool.id);
      setShowConfig(false);
    } catch (error) {
      console.error('Failed to generate grouping plan:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || !active.data.current || !currentPool) return;

    const phrase = active.data.current.phrase as string;
    const sourceGroupId = active.data.current.groupId as string;
    const targetGroupId = over.id as string;

    if (sourceGroupId === targetGroupId) return;

    // Optimistic UI update
    setGroups((prev) => {
      const updated = prev.map((group) => {
        if (group.id === sourceGroupId) {
          return { ...group, phrases: group.phrases.filter((p) => p !== phrase) };
        }
        if (group.id === targetGroupId) {
          return { ...group, phrases: [...group.phrases, phrase] };
        }
        return group;
      });
      return updated;
    });

    // Track override (non-blocking)
    await addOverride(currentPool.id, {
      phrase,
      action: 'move',
      sourceGroupId,
      targetGroupLabel: groups.find((g) => g.id === targetGroupId)?.label,
      targetGroupIndex: groups.findIndex((g) => g.id === targetGroupId),
    });
  };

  const handleUpdateLabel = async (groupId: string, newLabel: string) => {
    // Update locally
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, label: newLabel } : g))
    );
    // TODO: Call API to persist label change
  };

  const handleApprove = async () => {
    if (!currentPool || !canApprove) return;

    const result = await approveGrouping(currentPool.id);
    if (result) {
      // Success - pool status updated to 'grouped'
      if (onContinue) onContinue();
    }
  };

  const handleUnapprove = async () => {
    if (!currentPool) return;

    await unapproveGrouping(currentPool.id);
  };

  const handleReset = async () => {
    if (!currentPool) return;

    await resetOverrides(currentPool.id);
    await loadGroups(currentPool.id);
  };

  // Progress indicator
  const getProgressState = () => {
    if (!currentPool) return 'Configure';
    if (currentPool.status === 'grouped') return 'Approved ✓';
    if (groups.length > 0) return 'Review';
    return 'Configure';
  };

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="flex gap-4 border-b">
        <button
          onClick={() => setActiveTab('body')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'body'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Description & Bullets Pool
        </button>
        <button
          onClick={() => setActiveTab('titles')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'titles'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Titles Pool
        </button>
      </div>

      {/* Progress Indicator */}
      <div className="flex items-center justify-center gap-2 text-sm">
        <span className={getProgressState() === 'Configure' ? 'font-bold' : 'text-gray-500'}>
          Configure
        </span>
        <span className="text-gray-400">→</span>
        <span className={getProgressState() === 'Review' ? 'font-bold' : 'text-gray-500'}>
          Review
        </span>
        <span className="text-gray-400">→</span>
        <span className={getProgressState().startsWith('Approved') ? 'font-bold text-green-600' : 'text-gray-500'}>
          Approve
        </span>
      </div>

      {/* Configuration Form */}
      {showConfig && (
        <GroupingConfigForm onGenerate={handleGenerate} isGenerating={isGenerating} />
      )}

      {/* Groups Display */}
      {groups.length > 0 && (
        <>
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Keyword Groups ({groups.length})</h2>
            <div className="flex gap-2">
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="px-3 py-1 text-sm border rounded hover:bg-gray-50"
              >
                {showConfig ? 'Hide' : 'Show'} Config
              </button>
              <button
                onClick={handleReset}
                className="px-3 py-1 text-sm border rounded hover:bg-gray-50"
              >
                Reset Overrides
              </button>
            </div>
          </div>

          <DndContext onDragEnd={handleDragEnd} collisionDetection={closestCenter}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {groups.map((group) => (
                <KeywordGroupCard key={group.id} group={group} onUpdateLabel={handleUpdateLabel} />
              ))}
            </div>
          </DndContext>

          {/* Approval Actions */}
          <div className="flex justify-between items-center pt-4 border-t">
            {isApproved ? (
              <div className="flex items-center gap-2">
                <span className="text-green-600 font-medium">✓ Grouping Approved</span>
                <button
                  onClick={handleUnapprove}
                  className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
                >
                  Unapprove
                </button>
              </div>
            ) : (
              <button
                onClick={handleApprove}
                disabled={!canApprove}
                className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                Approve Grouping
              </button>
            )}

            {isApproved && (
              <button
                onClick={onContinue}
                className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Continue to Asset Generation
              </button>
            )}
          </div>
        </>
      )}

      {/* Empty State */}
      {groups.length === 0 && !showConfig && (
        <div className="text-center py-12 text-gray-500">
          <p className="mb-4">No groups generated yet</p>
          <button
            onClick={() => setShowConfig(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Configure Grouping
          </button>
        </div>
      )}
    </div>
  );
}
