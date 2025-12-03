interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
    asin: string | null;
    updatedAt: string;
}

interface SkuCardProps {
    sku: Sku;
    keywordCount: number;
    questionCount: number;
    onEdit: () => void;
    onDelete: () => void;
}

const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
};

export function SkuCard({
    sku,
    keywordCount,
    questionCount,
    onEdit,
    onDelete,
}: SkuCardProps) {
    return (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-start justify-between">
                <div className="flex-1">
                    <h3 className="text-base font-semibold text-slate-900">
                        {sku.skuCode}
                    </h3>
                    {sku.productName && (
                        <p className="mt-1 text-sm text-slate-600">{sku.productName}</p>
                    )}
                    {sku.asin && (
                        <p className="mt-1 text-xs text-slate-500">ASIN: {sku.asin}</p>
                    )}
                </div>
            </div>

            <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
                <span>{keywordCount} keywords</span>
                <span>{questionCount} questions</span>
                <span>Updated {formatRelativeTime(sku.updatedAt)}</span>
            </div>

            <div className="mt-4 flex items-center gap-2">
                <button
                    onClick={onEdit}
                    className="flex-1 rounded-lg border border-[#0a6fd6] bg-white px-3 py-2 text-sm font-medium text-[#0a6fd6] transition-colors hover:bg-[#0a6fd6] hover:text-white"
                >
                    Edit SKU
                </button>
                <button
                    onClick={onDelete}
                    className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100"
                >
                    Delete
                </button>
            </div>
        </div>
    );
}
