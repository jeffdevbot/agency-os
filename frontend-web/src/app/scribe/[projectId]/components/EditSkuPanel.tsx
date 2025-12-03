"use client";

import { useState, useEffect } from "react";

interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
    asin: string | null;
    brandTone: string | null;
    targetAudience: string | null;
    suppliedContent: string | null;
    wordsToAvoid: string[] | null;
}

interface EditSkuPanelProps {
    projectId: string;
    sku: Sku | null; // null = creating new SKU
    customAttributes: string[];
    customAttributeValues?: Record<string, string>; // { "size": "8x10", "color": "Navy" }
    keywords?: string[];
    questions?: string[];
    onClose: () => void;
    onSave: () => void;
}

export function EditSkuPanel({
    projectId,
    sku,
    customAttributes,
    customAttributeValues,
    keywords,
    questions,
    onClose,
    onSave,
}: EditSkuPanelProps) {
    const [formData, setFormData] = useState({
        sku_code: "",
        product_name: "",
        asin: "",
        brand_tone: "",
        target_audience: "",
        supplied_content: "",
        words_to_avoid: "",
        keywords: "",
        questions: "",
    });

    const [customAttrs, setCustomAttrs] = useState<Record<string, string>>({});
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (sku) {
            setFormData({
                sku_code: sku.skuCode || "",
                product_name: sku.productName || "",
                asin: sku.asin || "",
                brand_tone: sku.brandTone || "",
                target_audience: sku.targetAudience || "",
                supplied_content: sku.suppliedContent || "",
                words_to_avoid: (sku.wordsToAvoid || []).join("|"),
                keywords: (keywords || []).join("|"),
                questions: (questions || []).join("|"),
            });
            setCustomAttrs(customAttributeValues || {});
        } else {
            // Reset form when creating new SKU
            setFormData({
                sku_code: "",
                product_name: "",
                asin: "",
                brand_tone: "",
                target_audience: "",
                supplied_content: "",
                words_to_avoid: "",
                keywords: "",
                questions: "",
            });
            setCustomAttrs({});
        }
    }, [sku?.id, keywords, questions, customAttributeValues]);

    const keywordCount = formData.keywords ? formData.keywords.split("|").filter(Boolean).length : 0;
    const questionCount = formData.questions ? formData.questions.split("|").filter(Boolean).length : 0;

    const canSave =
        formData.sku_code?.trim() &&
        formData.product_name?.trim();

    const handleSave = async () => {
        if (!canSave) return;

        // Validate limits
        if (keywordCount > 10) {
            setError("Maximum 10 keywords allowed. Please remove some keywords before saving.");
            return;
        }
        if (questionCount > 30) {
            setError("Maximum 30 questions allowed. Please remove some questions before saving.");
            return;
        }

        setSaving(true);
        setError(null);

        try {
            const payload = {
                sku_code: formData.sku_code.trim(),
                product_name: formData.product_name.trim(),
                asin: formData.asin.trim() || null,
                brand_tone: formData.brand_tone.trim() || null,
                target_audience: formData.target_audience.trim() || null,
                supplied_content: formData.supplied_content.trim() || null,
                words_to_avoid: formData.words_to_avoid.split("|").map((s) => s.trim()).filter(Boolean),
            };

            const url = sku
                ? `/api/scribe/projects/${projectId}/skus/${sku.id}`
                : `/api/scribe/projects/${projectId}/skus`;
            const method = sku ? "PATCH" : "POST";

            const res = await fetch(url, {
                method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body?.error?.message ?? "Failed to save SKU");
            }

            const savedSku = await res.json();
            const skuId = savedSku.id || sku?.id;

            if (!skuId) throw new Error("No SKU ID returned");

            // Fetch variant attributes once (for custom attributes)
            const attrsRes = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`);
            const attrs = attrsRes.ok ? await attrsRes.json() : [];

            // Run all operations in parallel
            await Promise.all([
                // Keywords: delete existing + save new
                (async () => {
                    try {
                        const existingKwRes = await fetch(`/api/scribe/projects/${projectId}/keywords?skuId=${skuId}`);
                        if (existingKwRes.ok) {
                            const existingKeywords = await existingKwRes.json();
                            await Promise.all(
                                existingKeywords.map((kw: any) =>
                                    fetch(`/api/scribe/projects/${projectId}/keywords?id=${kw.id}`, { method: "DELETE" })
                                )
                            );
                        }

                        const keywordList = formData.keywords.split("|").map((s) => s.trim()).filter(Boolean);
                        if (keywordList.length > 0) {
                            await Promise.all(
                                keywordList.map((keyword) =>
                                    fetch(`/api/scribe/projects/${projectId}/keywords`, {
                                        method: "POST",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify({ skuId, keyword }),
                                    })
                                )
                            );
                        }
                    } catch (err) {
                        console.error("Error saving keywords:", err);
                    }
                })(),

                // Questions: delete existing + save new
                (async () => {
                    try {
                        const existingQRes = await fetch(`/api/scribe/projects/${projectId}/questions?skuId=${skuId}`);
                        if (existingQRes.ok) {
                            const existingQuestions = await existingQRes.json();
                            await Promise.all(
                                existingQuestions.map((q: any) =>
                                    fetch(`/api/scribe/projects/${projectId}/questions?id=${q.id}`, { method: "DELETE" })
                                )
                            );
                        }

                        const questionList = formData.questions.split("|").map((s) => s.trim()).filter(Boolean);
                        if (questionList.length > 0) {
                            await Promise.all(
                                questionList.map((question) =>
                                    fetch(`/api/scribe/projects/${projectId}/questions`, {
                                        method: "POST",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify({ skuId, question }),
                                    })
                                )
                            );
                        }
                    } catch (err) {
                        console.error("Error saving questions:", err);
                    }
                })(),

                // Custom attributes: save all in parallel
                ...customAttributes.map(async (attrName) => {
                    const value = customAttrs[attrName];
                    if (!value) return;

                    try {
                        const attr = attrs.find((a: any) => a.name === attrName);
                        if (!attr) return;

                        await fetch(`/api/scribe/projects/${projectId}/variant-attributes/${attr.id}/values`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ skuId, value: value.trim() }),
                        });
                    } catch (err) {
                        console.error(`Failed to save custom attribute "${attrName}":`, err);
                    }
                }),
            ]);

            onSave();
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save");
        } finally {
            setSaving(false);
        }
    };

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 z-40 bg-black/30 transition-opacity"
                onClick={onClose}
            />

            {/* Slide-over Panel */}
            <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-white shadow-xl">
                {/* Header */}
                <div className="border-b border-slate-200 px-6 py-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-lg font-semibold text-slate-900">
                            {sku ? "Edit SKU" : "Add SKU"}
                        </h2>
                        <button
                            onClick={onClose}
                            className="text-slate-400 hover:text-slate-600"
                        >
                            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto px-6 py-6">
                    <div className="space-y-6">
                        {/* Core Identifiers */}
                        <div>
                            <h3 className="text-sm font-medium text-slate-700">Core Information</h3>
                            <div className="mt-3 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">
                                        SKU Code <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        value={formData.sku_code}
                                        onChange={(e) => setFormData({ ...formData, sku_code: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">
                                        Product Name <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        value={formData.product_name}
                                        onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">ASIN</label>
                                    <input
                                        type="text"
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        value={formData.asin}
                                        onChange={(e) => setFormData({ ...formData, asin: e.target.value })}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Brand Metadata */}
                        <div>
                            <h3 className="text-sm font-medium text-slate-700">Brand Metadata</h3>
                            <div className="mt-3 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">Brand Tone</label>
                                    <textarea
                                        rows={3}
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        placeholder="e.g., Friendly, professional, approachable"
                                        value={formData.brand_tone}
                                        onChange={(e) => setFormData({ ...formData, brand_tone: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">Target Audience</label>
                                    <textarea
                                        rows={2}
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        placeholder="e.g., Small business owners, creative professionals"
                                        value={formData.target_audience}
                                        onChange={(e) => setFormData({ ...formData, target_audience: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">Supplied Content</label>
                                    <textarea
                                        rows={4}
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        placeholder="Any existing copy or content to reference"
                                        value={formData.supplied_content}
                                        onChange={(e) => setFormData({ ...formData, supplied_content: e.target.value })}
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Multi-Value Lists */}
                        <div>
                            <h3 className="text-sm font-medium text-slate-700">Multi-Value Lists</h3>
                            <div className="mt-3 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700">Words to Avoid</label>
                                    <textarea
                                        rows={2}
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        placeholder="word1|word2|word3"
                                        value={formData.words_to_avoid}
                                        onChange={(e) => setFormData({ ...formData, words_to_avoid: e.target.value })}
                                    />
                                    <p className="mt-1 text-xs text-slate-500">
                                        Enter multiple values separated by pipes (|)
                                    </p>
                                </div>
                                <div>
                                    <div className="flex items-center justify-between">
                                        <label className="block text-sm font-medium text-slate-700">Keywords</label>
                                        <span className={`text-xs ${keywordCount > 10 ? "text-red-600" : "text-slate-500"}`}>
                                            {keywordCount} / 10
                                        </span>
                                    </div>
                                    <textarea
                                        rows={2}
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        placeholder="keyword1|keyword2|keyword3"
                                        value={formData.keywords}
                                        onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
                                    />
                                    <p className="mt-1 text-xs text-slate-500">
                                        Maximum 10 keywords. Enter multiple values separated by pipes (|)
                                    </p>
                                </div>
                                <div>
                                    <div className="flex items-center justify-between">
                                        <label className="block text-sm font-medium text-slate-700">Questions</label>
                                        <span className={`text-xs ${questionCount > 30 ? "text-red-600" : "text-slate-500"}`}>
                                            {questionCount} / 30
                                        </span>
                                    </div>
                                    <textarea
                                        rows={3}
                                        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                        placeholder="question1|question2|question3"
                                        value={formData.questions}
                                        onChange={(e) => setFormData({ ...formData, questions: e.target.value })}
                                    />
                                    <p className="mt-1 text-xs text-slate-500">
                                        Maximum 30 questions. Enter multiple values separated by pipes (|)
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Custom Attributes */}
                        {customAttributes.length > 0 && (
                            <div>
                                <h3 className="text-sm font-medium text-slate-700">Custom Attributes</h3>
                                <div className="mt-3 space-y-4">
                                    {customAttributes.map((attr) => (
                                        <div key={attr}>
                                            <label className="block text-sm font-medium capitalize text-slate-700">
                                                {attr}
                                            </label>
                                            <input
                                                type="text"
                                                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                                value={customAttrs[attr] || ""}
                                                onChange={(e) =>
                                                    setCustomAttrs({ ...customAttrs, [attr]: e.target.value })
                                                }
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="border-t border-slate-200 px-6 py-4">
                    {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
                    <div className="flex items-center justify-between">
                        <p className="text-xs text-slate-500">
                            Changes will mark downstream stages as stale
                        </p>
                        <div className="flex gap-3">
                            <button
                                onClick={onClose}
                                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                                disabled={saving}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSave}
                                disabled={!canSave || saving}
                                className="rounded-lg bg-[#0a6fd6] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {saving ? "Saving..." : "Save Changes"}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
