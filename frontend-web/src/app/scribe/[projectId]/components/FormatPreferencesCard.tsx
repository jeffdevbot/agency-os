"use client";

import { useState, useEffect } from "react";

interface FormatPreferences {
    bulletCapsHeaders?: boolean;
    descriptionParagraphs?: boolean;
}

interface FormatPreferencesCardProps {
    projectId: string;
    initialPreferences?: FormatPreferences | null;
    onPreferencesChange?: () => void;
}

const DEFAULT_PREFERENCES: FormatPreferences = {
    bulletCapsHeaders: false,
    descriptionParagraphs: true,
};

export function FormatPreferencesCard({
    projectId,
    initialPreferences,
    onPreferencesChange,
}: FormatPreferencesCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [preferences, setPreferences] = useState<FormatPreferences>(
        initialPreferences ?? DEFAULT_PREFERENCES
    );
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (initialPreferences) {
            setPreferences({
                bulletCapsHeaders: initialPreferences.bulletCapsHeaders ?? false,
                descriptionParagraphs: initialPreferences.descriptionParagraphs ?? true,
            });
        }
    }, [initialPreferences]);

    const handleToggle = async (key: keyof FormatPreferences) => {
        const newPreferences = {
            ...preferences,
            [key]: !preferences[key],
        };

        setPreferences(newPreferences);
        setSaving(true);
        setError(null);

        try {
            const res = await fetch(`/api/scribe/projects/${projectId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ formatPreferences: newPreferences }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error?.message || "Failed to save preferences");
            }

            if (onPreferencesChange) {
                onPreferencesChange();
            }
        } catch (err) {
            // Revert on error
            setPreferences(preferences);
            setError(err instanceof Error ? err.message : "Failed to save preferences");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="border-b border-slate-200">
            {/* Header - Collapsible */}
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex w-full items-center justify-between p-6 text-left transition-colors hover:bg-slate-50"
            >
                <div>
                    <h3 className="text-sm font-semibold text-slate-800">
                        <span className="mr-2">{isExpanded ? "▼" : "▶"}</span>
                        Copy Formatting
                    </h3>
                    <p className="mt-1 text-xs text-slate-600">
                        Customize bullet formatting and description layout.
                    </p>
                </div>
            </button>

            {/* Expanded Content */}
            {isExpanded && (
                <div className="border-t border-slate-200 p-6">
                    {error && (
                        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3">
                            <p className="text-sm text-red-800">{error}</p>
                        </div>
                    )}

                    <div className="space-y-4">
                        {/* ALL CAPS Headers Toggle */}
                        <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 pt-0.5">
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={preferences.bulletCapsHeaders}
                                    onClick={() => handleToggle("bulletCapsHeaders")}
                                    disabled={saving}
                                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#0a6fd6] focus:ring-offset-2 disabled:opacity-50 ${
                                        preferences.bulletCapsHeaders ? "bg-[#0a6fd6]" : "bg-slate-200"
                                    }`}
                                >
                                    <span
                                        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                            preferences.bulletCapsHeaders ? "translate-x-4" : "translate-x-0"
                                        }`}
                                    />
                                </button>
                            </div>
                            <div className="flex-1">
                                <label
                                    className="text-sm font-medium text-slate-800 cursor-pointer"
                                    onClick={() => handleToggle("bulletCapsHeaders")}
                                >
                                    ALL CAPS bullet headers
                                </label>
                                <p className="text-xs text-slate-600 mt-0.5">
                                    Start each bullet with an uppercase header followed by a colon.
                                </p>
                                <div className="mt-2 rounded-lg bg-slate-50 p-3 border border-slate-200">
                                    <p className="text-xs text-slate-500 mb-1">Example:</p>
                                    <p className="text-xs text-slate-700 font-mono">
                                        <span className="font-semibold">UNMATCHED QUALITY:</span> Aluminum wall photo
                                        frame available in a variety of sizes. A 0.4" wide and 0.8" deep frame provides
                                        a contemporary and sleek look...
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Description Paragraphs Toggle */}
                        <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 pt-0.5">
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={preferences.descriptionParagraphs}
                                    onClick={() => handleToggle("descriptionParagraphs")}
                                    disabled={saving}
                                    className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#0a6fd6] focus:ring-offset-2 disabled:opacity-50 ${
                                        preferences.descriptionParagraphs ? "bg-[#0a6fd6]" : "bg-slate-200"
                                    }`}
                                >
                                    <span
                                        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                            preferences.descriptionParagraphs ? "translate-x-4" : "translate-x-0"
                                        }`}
                                    />
                                </button>
                            </div>
                            <div className="flex-1">
                                <label
                                    className="text-sm font-medium text-slate-800 cursor-pointer"
                                    onClick={() => handleToggle("descriptionParagraphs")}
                                >
                                    Paragraph breaks in description
                                </label>
                                <p className="text-xs text-slate-600 mt-0.5">
                                    Separate key topics with line breaks for better readability.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
