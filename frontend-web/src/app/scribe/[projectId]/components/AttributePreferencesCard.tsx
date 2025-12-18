"use client";

import { useState, useEffect } from "react";

interface AttributePreferencesCardProps {
    projectId: string;
    skus: Array<{ id: string; skuCode: string }>;
    variantAttributes: Array<{ id: string; name: string; slug: string; sort_order: number }>;
    onPreferencesChange?: () => void;
}

interface AttributePreferences {
    mode: "auto" | "overrides";
    rules?: Record<string, { sections: string[] }>;
}

export function AttributePreferencesCard({
    projectId,
    skus,
    variantAttributes,
    onPreferencesChange,
}: AttributePreferencesCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [preferences, setPreferences] = useState<Record<string, Set<string>>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadPreferences();
    }, [skus, variantAttributes]);

    const loadPreferences = async () => {
        if (skus.length === 0 || variantAttributes.length === 0) {
            setLoading(false);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            // Note: We don't have a GET endpoint for individual SKUs
            // So we start with empty preferences (auto mode)
            // When user toggles checkboxes, we'll save to all SKUs via PATCH
            const prefs: Record<string, Set<string>> = {};

            console.log("✅ Initialized with empty preferences (auto mode)");
            setPreferences(prefs);
        } catch (err) {
            console.error("💥 Error loading preferences:", err);
            setError(err instanceof Error ? err.message : "Failed to load preferences");
        } finally {
            setLoading(false);
        }
    };

    const handleToggle = async (attributeName: string, section: string) => {
        console.log(`🔄 Toggle clicked: ${attributeName} - ${section}`);

        // Optimistic update
        const currentSections = preferences[attributeName] || new Set();
        const newSections = new Set(currentSections);

        if (newSections.has(section)) {
            console.log(`  ❌ Unchecking ${section}`);
            newSections.delete(section);
        } else {
            console.log(`  ✅ Checking ${section}`);
            newSections.add(section);
        }

        const newPreferences = {
            ...preferences,
            [attributeName]: newSections,
        };

        console.log("📊 New preferences state:", newPreferences);
        setPreferences(newPreferences);

        // Build attribute preferences payload
        const attributePrefsPayload = buildAttributePrefs(newPreferences);
        console.log("📤 Payload to send:", JSON.stringify(attributePrefsPayload, null, 2));

        // Save to ALL SKUs
        try {
            console.log(`💾 Saving to ${skus.length} SKUs...`);
            const responses = await Promise.all(
                skus.map((sku) =>
                    fetch(`/api/scribe/projects/${projectId}/skus/${sku.id}`, {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ attribute_preferences: attributePrefsPayload }),
                    })
                )
            );

            // Check if all responses were successful
            const allSuccess = responses.every(r => r.ok);
            if (allSuccess) {
                console.log("✅ Successfully saved preferences to all SKUs");
            } else {
                console.error("⚠️ Some SKUs failed to save:", responses.filter(r => !r.ok));
            }

            // Notify parent if callback provided
            if (onPreferencesChange) {
                onPreferencesChange();
            }
        } catch (err) {
            console.error("❌ Error saving preferences:", err);
            // Revert optimistic update on error
            setPreferences(preferences);
            setError(err instanceof Error ? err.message : "Failed to save preferences");
        }
    };

    const buildAttributePrefs = (prefs: Record<string, Set<string>>): AttributePreferences | null => {
        // Check if any checkboxes are selected
        const hasAnySelection = Object.values(prefs).some((sections) => sections.size > 0);

        if (!hasAnySelection) {
            return null; // Auto mode
        }

        // Build rules object
        const rules: Record<string, { sections: string[] }> = {};
        Object.entries(prefs).forEach(([attrName, sections]) => {
            if (sections.size > 0) {
                rules[attrName] = { sections: Array.from(sections) };
            }
        });

        return {
            mode: "overrides",
            rules,
        };
    };

    const isChecked = (attributeName: string, section: string): boolean => {
        const attrPrefs = preferences[attributeName];
        return attrPrefs ? attrPrefs.has(section) : false;
    };

    // Hide card if no variant attributes
    if (variantAttributes.length === 0) {
        return null;
    }

    return (
        <div className="mb-6 rounded-lg border border-slate-200 bg-white">
            {/* Header - Collapsible */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex w-full items-center justify-between p-6 text-left transition-colors hover:bg-slate-50"
            >
                <div>
                    <h3 className="text-sm font-semibold text-slate-800">
                        <span className="mr-2">{isExpanded ? "▼" : "▶"}</span>
                        Attribute Preferences{" "}
                    </h3>
                    <p className="mt-1 text-xs text-slate-600">
                        By default, AI naturally incorporates attributes into your content. Use this to enforce specific placements.
                    </p>
                </div>
            </button>

            {/* Expanded Content */}
            {isExpanded && (
                <div className="border-t border-slate-200 p-6">
                    <p className="mb-4 text-xs text-slate-600">
                        Check the boxes below to require specific attributes in specific sections. Leave all unchecked to let the AI decide naturally.
                    </p>

                    <div className="mb-4 rounded-lg bg-blue-50 p-3">
                        <p className="text-xs text-blue-800">
                            💡 <strong>Example:</strong> Selling a red t-shirt? Check "Bullets" under "Color" to ensure the bullets include "Red" where it matters most.
                        </p>
                    </div>

                    {error && (
                        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3">
                            <p className="text-sm text-red-800">{error}</p>
                        </div>
                    )}

                    {loading && (
                        <p className="py-4 text-center text-sm text-slate-600">Loading preferences...</p>
                    )}

                    {!loading && (
                        <>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-slate-200">
                                            <th className="pb-3 pr-4 text-left font-medium text-slate-700">
                                                Attribute
                                            </th>
                                            <th className="px-4 pb-3 text-center font-medium text-slate-700">
                                                Bullets
                                            </th>
                                            <th className="px-4 pb-3 text-center font-medium text-slate-700">
                                                Description
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {variantAttributes
                                            .sort((a, b) => a.sort_order - b.sort_order)
                                            .map((attr) => (
                                                <tr key={attr.id} className="border-b border-slate-100">
                                                    <td className="py-3 pr-4 font-medium text-slate-800">
                                                        {attr.name}
                                                    </td>
                                                    <td className="px-4 py-3 text-center">
                                                        <input
                                                            type="checkbox"
                                                            checked={isChecked(attr.name, "bullets")}
                                                            onChange={() => handleToggle(attr.name, "bullets")}
                                                            className="h-4 w-4 rounded border-slate-300 text-[#0a6fd6] focus:ring-[#0a6fd6]"
                                                        />
                                                    </td>
                                                    <td className="px-4 py-3 text-center">
                                                        <input
                                                            type="checkbox"
                                                            checked={isChecked(attr.name, "description")}
                                                            onChange={() => handleToggle(attr.name, "description")}
                                                            className="h-4 w-4 rounded border-slate-300 text-[#0a6fd6] focus:ring-[#0a6fd6]"
                                                        />
                                                    </td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>

                            <div className="mt-4 flex items-start gap-2 rounded-lg bg-slate-50 p-3">
                                <svg
                                    className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-500"
                                    fill="currentColor"
                                    viewBox="0 0 20 20"
                                >
                                    <path
                                        fillRule="evenodd"
                                        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                                <p className="text-xs text-slate-600">
                                    These preferences apply to all SKUs in this project
                                </p>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
