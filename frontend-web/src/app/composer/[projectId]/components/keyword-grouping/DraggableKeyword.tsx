'use client';

import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';

interface DraggableKeywordProps {
  phrase: string;
  groupId: string;
}

export function DraggableKeyword({ phrase, groupId }: DraggableKeywordProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: phrase,
    data: { phrase, groupId },
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className="px-3 py-1.5 bg-gray-100 rounded-md text-sm cursor-move hover:bg-gray-200 transition-colors"
    >
      {phrase}
    </div>
  );
}
