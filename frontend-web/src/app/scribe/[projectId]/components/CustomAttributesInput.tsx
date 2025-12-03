"use client";

import { useState, useEffect } from "react";

interface CustomAttributesInputProps {
    projectId: string;
    initialAttributes?: string[];
    onSave?: (attributes: string[]) => void;
}

export function CustomAttributesInput({
    projectId,
    initialAttributes = [],
    onSave,
}: CustomAttributesInputProps) {
    const [value, setValue] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Convert array to pipe-separated string for display
        setValue(initialAttributes.join("|"));
    }, [initialAttributes]);

    const handleBlur = async () => {
        const trimmed = value.trim();
        const attributes = trimmed ? trimmed.split("|").map((s) => s.trim()).filter(Boolean) : [];

        // Only save if changed
        const unchanged =
            attributes.length === initialAttributes.length &&
            attributes.every((attr, i) => attr === initialAttributes[i]);

        if (unchanged) return;

        setSaving(true);
        setError(null);

        try {
            // Fetch existing variant attributes
            const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`);
            if (!res.ok) throw new Error("Failed to fetch existing attributes");

            const existing = await res.json();
            const existingNames = existing.map((attr: any) => attr.name);

            // Delete removed attributes
            for (const attr of existing) {
                if (!attributes.includes(attr.name)) {
                    await fetch(`/api/scribe/projects/${projectId}/variant-attributes?id=${attr.id}`, {
                        method: "DELETE",
                    });
                }
            }

            // Create new attributes
            for (const attrName of attributes) {
                if (!existingNames.includes(attrName)) {
                    await fetch(`/api/scribe/projects/${projectId}/variant-attributes`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ name: attrName }),
                    });
                }
            }

            onSave?.(attributes);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <label className="block text-sm font-medium text-slate-700">
                Custom Attributes (Optional)
            </label>
            <p className="mt-1 text-xs text-slate-500">
                Define extra attributes for your SKUs (e.g., size, color, material). Separate with pipes.
            </p>
            <input
                type="text"
                className="mt-2 w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-[#0a6fd6] focus:outline-none focus:ring-1 focus:ring-[#0a6fd6]"
                placeholder="size|color|material|pack size"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onBlur={handleBlur}
                disabled={saving}
            />
            {saving && <p className="mt-1 text-xs text-slate-500">Saving...</p>}
            {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
        </div>
    );
}
