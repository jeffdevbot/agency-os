'use client';

import { useState } from 'react';
import type { GroupingConfig } from './types';

interface GroupingConfigFormProps {
  onGenerate: (config: GroupingConfig) => void;
  isGenerating?: boolean;
}

export function GroupingConfigForm({ onGenerate, isGenerating }: GroupingConfigFormProps) {
  const [basis, setBasis] = useState<GroupingConfig['basis']>('single');
  const [attributeName, setAttributeName] = useState('');
  const [groupCount, setGroupCount] = useState<number>(3);
  const [phrasesPerGroup, setPhrasesPerGroup] = useState<number>(10);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const config: GroupingConfig = {
      basis,
      ...(basis === 'attribute' && attributeName ? { attributeName } : {}),
      ...(basis === 'custom' ? { groupCount, phrasesPerGroup } : {}),
    };

    onGenerate(config);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 border rounded-lg bg-gray-50">
      <div>
        <label className="block text-sm font-medium mb-2">Grouping Strategy</label>
        <select
          value={basis}
          onChange={(e) => setBasis(e.target.value as GroupingConfig['basis'])}
          className="w-full px-3 py-2 border rounded-md"
          disabled={isGenerating}
        >
          <option value="single">Single Group (All Keywords Together)</option>
          <option value="per_sku">One Group Per SKU</option>
          <option value="attribute">Group By Product Attribute</option>
          <option value="custom">Custom Grouping</option>
        </select>
      </div>

      {basis === 'attribute' && (
        <div>
          <label className="block text-sm font-medium mb-2">Attribute Name</label>
          <input
            type="text"
            value={attributeName}
            onChange={(e) => setAttributeName(e.target.value)}
            placeholder="e.g., color, size, style"
            className="w-full px-3 py-2 border rounded-md"
            required
            disabled={isGenerating}
          />
        </div>
      )}

      {basis === 'custom' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Number of Groups</label>
            <input
              type="number"
              value={groupCount}
              onChange={(e) => setGroupCount(parseInt(e.target.value) || 3)}
              min="1"
              max="20"
              className="w-full px-3 py-2 border rounded-md"
              disabled={isGenerating}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Keywords Per Group</label>
            <input
              type="number"
              value={phrasesPerGroup}
              onChange={(e) => setPhrasesPerGroup(parseInt(e.target.value) || 10)}
              min="1"
              max="100"
              className="w-full px-3 py-2 border rounded-md"
              disabled={isGenerating}
            />
          </div>
        </div>
      )}

      <button
        type="submit"
        disabled={isGenerating}
        className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {isGenerating ? 'Generating Groups...' : 'Generate Grouping Plan'}
      </button>
    </form>
  );
}
