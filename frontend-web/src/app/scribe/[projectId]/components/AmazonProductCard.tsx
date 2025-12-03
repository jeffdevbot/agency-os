"use client";

interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
}

interface GeneratedContent {
    id: string;
    title: string;
    bullets: string[];
    description: string;
    backendKeywords: string;
}

interface AmazonProductCardProps {
    sku: Sku;
    content: GeneratedContent;
    isExpanded: boolean;
    onToggleExpand: () => void;
    onEdit: () => void;
    onRegenerate: () => void;
}

export function AmazonProductCard({
    sku,
    content,
    isExpanded,
    onToggleExpand,
    onEdit,
    onRegenerate,
}: AmazonProductCardProps) {
    return (
        <div className="rounded-lg border border-[#FF9900] bg-[#FFFBF5] shadow-sm">
            {/* Card Header (outside Amazon mockup) */}
            <div className="flex items-center justify-between border-b border-[#FF9900]/20 bg-white px-6 py-4">
                <button
                    onClick={onToggleExpand}
                    className="flex flex-1 items-center gap-3 text-left"
                >
                    <svg
                        className={`h-5 w-5 text-slate-400 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    <div>
                        <h3 className="font-semibold text-slate-800">{sku.skuCode}</h3>
                        {sku.productName && (
                            <p className="text-sm text-slate-600">{sku.productName}</p>
                        )}
                        {!isExpanded && (
                            <p className="mt-1 text-sm text-slate-500 line-clamp-1">{content.title}</p>
                        )}
                    </div>
                </button>
                <div className="flex items-center gap-2">
                    <button
                        onClick={onEdit}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                        Edit
                    </button>
                    <button
                        onClick={onRegenerate}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                        Regenerate
                    </button>
                </div>
            </div>

            {/* Amazon Product Page Mockup */}
            {isExpanded && (
                <div className="p-6">
                    {/* 2-Column Layout */}
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-[300px_1fr]">
                        {/* Column 1: Product Images */}
                        <div className="flex gap-3">
                            {/* Thumbnail Strip (vertical) */}
                            <div className="flex flex-col gap-2">
                                {[1, 2, 3, 4].map((i) => (
                                    <div
                                        key={i}
                                        className="flex h-12 w-12 items-center justify-center rounded border border-[#FF9900]/30 bg-[#FF9900]/10"
                                    >
                                        <svg
                                            className="h-6 w-6 text-[#FF9900]/40"
                                            fill="none"
                                            stroke="currentColor"
                                            viewBox="0 0 24 24"
                                        >
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                                            />
                                        </svg>
                                    </div>
                                ))}
                            </div>
                            {/* Hero Image */}
                            <div className="flex flex-1 items-center justify-center rounded border border-[#FF9900]/30 bg-[#FF9900]/10 p-8">
                                <svg
                                    className="h-24 w-24 text-[#FF9900]/40"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                                    />
                                </svg>
                            </div>
                        </div>

                        {/* Column 2: Product Details */}
                        <div className="space-y-4">
                            {/* Title */}
                            <h2 className="text-base font-bold leading-snug text-slate-900 md:text-lg">
                                {content.title}
                            </h2>

                            {/* Mock Reviews */}
                            <div className="flex items-center gap-2">
                                <div className="flex items-center">
                                    <span className="text-sm font-semibold text-slate-900">5.0</span>
                                    <span className="ml-1 text-[#FF9900]">★★★★★</span>
                                </div>
                                <span className="text-sm text-[#007185] hover:underline">125 ratings</span>
                            </div>

                            {/* Mock Price */}
                            <div className="text-2xl font-normal text-slate-900">$XX.XX</div>

                            {/* Divider */}
                            <div className="border-t border-slate-200" />

                            {/* About this item */}
                            <div>
                                <h3 className="mb-2 text-base font-bold text-slate-900">About this item</h3>
                                <ul className="space-y-2">
                                    {content.bullets.map((bullet, index) => (
                                        <li key={index} className="flex items-start gap-2 text-sm text-slate-800">
                                            <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-slate-800" />
                                            <span className="flex-1">{bullet}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </div>

                    {/* Description Section (Full-width below columns) */}
                    <div className="mt-6 space-y-3 border-t border-slate-200 pt-6">
                        <h3 className="text-base font-bold text-slate-900">Product Description</h3>
                        <div className="whitespace-pre-line text-sm leading-relaxed text-slate-800">
                            {content.description}
                        </div>
                    </div>

                    {/* Backend Keywords Box (Separate, below mockup) */}
                    <div className="mt-6 rounded border border-slate-200 bg-slate-100 p-4">
                        <h4 className="mb-2 text-sm font-semibold text-slate-700">Backend Keywords</h4>
                        <p className="text-sm text-slate-600">{content.backendKeywords}</p>
                        <p className="mt-2 text-xs text-slate-500">
                            These keywords are not visible to customers but help with search discoverability on Amazon.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}
