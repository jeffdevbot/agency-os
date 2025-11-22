'use client';

import { useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import type { KeywordGroup } from './types';
import { DraggableKeyword } from './DraggableKeyword';

interface KeywordGroupCardProps {
  group: KeywordGroup;
  onUpdateLabel?: (groupId: string, newLabel: string) => void;
}

export function KeywordGroupCard({ group, onUpdateLabel }: KeywordGroupCardProps) {
  const { setNodeRef, isOver } = useDroppable({ id: group.groupIndex.toString() });
  const [isEditing, setIsEditing] = useState(false);
  const [labelValue, setLabelValue] = useState(group.label ?? "");
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleSaveLabel = () => {
    if (onUpdateLabel && labelValue.trim() !== group.label) {
      onUpdateLabel(group.groupIndex.toString(), labelValue.trim());
    }
    setIsEditing(false);
  };

  return (
    <div
      ref={setNodeRef}
      className={`border rounded-lg p-4 ${
        isOver ? 'bg-blue-50 border-blue-300' : 'bg-white border-gray-200'
      } transition-colors`}
    >
      <div className="flex items-center justify-between mb-3">
        {isEditing ? (
          <input
            type="text"
            value={labelValue}
            onChange={(e) => setLabelValue(e.target.value)}
            onBlur={handleSaveLabel}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveLabel();
              if (e.key === 'Escape') {
                setLabelValue(group.label);
                setIsEditing(false);
              }
            }}
            className="flex-1 px-2 py-1 border rounded text-sm mr-2"
            autoFocus
          />
        ) : (
          <h3
            className="font-medium text-sm cursor-pointer hover:text-blue-600"
            onClick={() => setIsEditing(true)}
          >
            {group.label}
          </h3>
        )}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{group.phrases.length} keywords</span>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="text-gray-400 hover:text-gray-600"
          >
            {isCollapsed ? '▶' : '▼'}
          </button>
        </div>
      </div>

      {!isCollapsed && (
        <div className="flex flex-wrap gap-2 max-h-[400px] overflow-y-auto">
          {group.phrases.map((phrase) => (
            <DraggableKeyword
              key={`${group.groupIndex}-${phrase}`}
              phrase={phrase}
              groupIndex={group.groupIndex}
            />
          ))}
        </div>
      )}
    </div>
  );
}
