interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
}

interface Topic {
    id: string;
    skuId: string;
    topicIndex: number;
    title: string;
    description: string | null;
    selected: boolean;
}

interface SkuTopicsCardProps {
    sku: Sku;
    topics: Topic[];
    onToggleTopic: (topicId: string) => void;
}

export function SkuTopicsCard({ sku, topics, onToggleTopic }: SkuTopicsCardProps) {
    const selectedCount = topics.filter((t) => t.selected).length;
    const isComplete = selectedCount === 5;
    const displayName = sku.productName || sku.skuCode;

    return (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            {/* Header */}
            <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
                <div>
                    <h3 className="text-lg font-semibold text-slate-800">{displayName}</h3>
                    <p className="text-sm text-slate-500">SKU: {sku.skuCode}</p>
                </div>
                <div className="flex items-center gap-2">
                    <span
                        className={`text-sm font-medium ${
                            isComplete
                                ? "text-green-600"
                                : selectedCount > 5
                                ? "text-red-600"
                                : "text-slate-600"
                        }`}
                    >
                        {selectedCount} / 5 selected
                    </span>
                    {isComplete && (
                        <svg
                            data-testid="complete-check"
                            className="h-5 w-5 text-green-600"
                            fill="currentColor"
                            viewBox="0 0 20 20"
                        >
                            <path
                                fillRule="evenodd"
                                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                clipRule="evenodd"
                            />
                        </svg>
                    )}
                </div>
            </div>

            {/* Topics List */}
            {topics.length === 0 ? (
                <p className="text-sm text-slate-500">No topics generated for this SKU</p>
            ) : (
                <div className="space-y-3">
                    {topics.map((topic) => (
                        <label
                            key={topic.id}
                            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                                topic.selected
                                    ? "border-[#0a6fd6] bg-blue-50"
                                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                            }`}
                        >
                            <input
                                type="checkbox"
                                checked={topic.selected}
                                onChange={() => onToggleTopic(topic.id)}
                                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-[#0a6fd6] focus:ring-[#0a6fd6]"
                            />
                            <div className="flex-1">
                                <p className="text-sm font-medium text-slate-800">{topic.title}</p>
                                {topic.description && (
                                    <p className="mt-1 whitespace-pre-line text-xs text-slate-600">{topic.description}</p>
                                )}
                            </div>
                        </label>
                    ))}
                </div>
            )}
        </div>
    );
}
