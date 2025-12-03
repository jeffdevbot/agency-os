"use client";

import { useState, useEffect } from "react";

interface GeneratedContent {
    id: string;
    title: string;
    bullets: string[];
    description: string;
    backendKeywords: string;
}

interface EditGeneratedContentPanelProps {
    skuId: string;
    content: GeneratedContent;
    onSave: (skuId: string, updates: { title: string; bullets: string[]; description: string }) => Promise<void>;
    onClose: () => void;
}

export function EditGeneratedContentPanel({
    skuId,
    content,
    onSave,
    onClose,
}: EditGeneratedContentPanelProps) {
    const [formData, setFormData] = useState({
        title: "",
        bullet1: "",
        bullet2: "",
        bullet3: "",
        bullet4: "",
        bullet5: "",
        description: "",
    });

    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setFormData({
            title: content.title || "",
            bullet1: content.bullets[0] || "",
            bullet2: content.bullets[1] || "",
            bullet3: content.bullets[2] || "",
            bullet4: content.bullets[3] || "",
            bullet5: content.bullets[4] || "",
            description: content.description || "",
        });
    }, [content]);

    const handleSave = async () => {
        setSaving(true);
        setError(null);

        try {
            // Validate character limits
            if (formData.title.length > 200) {
                throw new Error("Title must not exceed 200 characters");
            }

            const bullets = [
                formData.bullet1,
                formData.bullet2,
                formData.bullet3,
                formData.bullet4,
                formData.bullet5,
            ];

            for (let i = 0; i < bullets.length; i++) {
                if (bullets[i].length > 500) {
                    throw new Error(`Bullet ${i + 1} must not exceed 500 characters`);
                }
            }

            if (formData.description.length > 2000) {
                throw new Error("Description must not exceed 2000 characters");
            }

            await onSave(skuId, {
                title: formData.title.trim(),
                bullets: bullets.map((b) => b.trim()),
                description: formData.description.trim(),
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save changes");
        } finally {
            setSaving(false);
        }
    };

    const canSave = formData.title.trim() && formData.bullet1.trim();

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
                <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
                    <h2 className="text-lg font-semibold text-slate-800">Edit Generated Content</h2>
                    <button
                        onClick={onClose}
                        className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                    >
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto px-6 py-6">
                    <div className="space-y-6">
                        {/* Error Message */}
                        {error && (
                            <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                                <p className="text-sm text-red-800">{error}</p>
                            </div>
                        )}

                        {/* Title */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700">
                                Title <span className="text-red-500">*</span>
                                <span className="ml-2 text-slate-500">({formData.title.length}/200 characters)</span>
                            </label>
                            <input
                                type="text"
                                value={formData.title}
                                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                maxLength={200}
                                className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                placeholder="Enter product title"
                            />
                        </div>

                        {/* Bullets */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700">
                                Bullet Points <span className="text-red-500">*</span>
                            </label>
                            <p className="mt-1 text-xs text-slate-500">
                                5 bullet points required. Each bullet max 500 characters.
                            </p>
                            <div className="mt-3 space-y-3">
                                {[1, 2, 3, 4, 5].map((num) => {
                                    const key = `bullet${num}` as keyof typeof formData;
                                    const value = formData[key];
                                    return (
                                        <div key={num}>
                                            <label className="block text-xs font-medium text-slate-600">
                                                Bullet {num} ({value.length}/500 characters)
                                            </label>
                                            <textarea
                                                value={value}
                                                onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
                                                maxLength={500}
                                                rows={3}
                                                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                                placeholder={`Enter bullet point ${num}`}
                                            />
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Description */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700">
                                Description <span className="text-red-500">*</span>
                                <span className="ml-2 text-slate-500">({formData.description.length}/2000 characters)</span>
                            </label>
                            <textarea
                                value={formData.description}
                                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                maxLength={2000}
                                rows={8}
                                className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                                placeholder="Enter product description"
                            />
                        </div>

                        {/* Backend Keywords (Display-only) */}
                        <div>
                            <label className="block text-sm font-medium text-slate-700">
                                Backend Keywords <span className="text-slate-500">(Display only)</span>
                            </label>
                            <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                                {content.backendKeywords}
                            </div>
                            <p className="mt-1 text-xs text-slate-500">
                                Backend keywords are not editable. Use Regenerate to create new keywords.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 border-t border-slate-200 px-6 py-4">
                    <button
                        onClick={onClose}
                        disabled={saving}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={!canSave || saving}
                        className="rounded-lg bg-[#0a6fd6] px-4 py-2 text-sm font-medium text-white hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {saving ? "Saving..." : "Save Changes"}
                    </button>
                </div>
            </div>
        </>
    );
}
