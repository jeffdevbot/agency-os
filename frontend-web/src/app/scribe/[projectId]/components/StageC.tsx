"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ScribeHeader } from "../../components/ScribeHeader";
import { ScribeProgressTracker } from "../../components/ScribeProgressTracker";
import { AttributePreferencesCard } from "./AttributePreferencesCard";
import { AmazonProductCard } from "./AmazonProductCard";
import { EditGeneratedContentPanel } from "./EditGeneratedContentPanel";
import { DirtyStateWarning } from "./DirtyStateWarning";

interface Project {
    id: string;
    name: string;
    locale: string;
}

interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
    updatedAt?: string;
}

interface VariantAttribute {
    id: string;
    name: string;
    slug: string;
    sort_order: number;
}

interface GeneratedContent {
    id: string;
    skuId: string;
    title: string;
    bullets: string[];
    description: string;
    backendKeywords: string;
    updatedAt: string;
}

export function StageC() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.projectId as string;

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [project, setProject] = useState<Project | null>(null);
    const [skus, setSkus] = useState<Sku[]>([]);
    const [variantAttributes, setVariantAttributes] = useState<VariantAttribute[]>([]);
    const [contentBySku, setContentBySku] = useState<Record<string, GeneratedContent>>({});
    const [generating, setGenerating] = useState(false);
    const [generatingType, setGeneratingType] = useState<'sample' | 'all' | null>(null);
    const [expandedSkus, setExpandedSkus] = useState<Set<string>>(new Set());
    const [editingSkuId, setEditingSkuId] = useState<string | null>(null);
    const [isDirty, setIsDirty] = useState(false);
    const [exporting, setExporting] = useState(false);

    useEffect(() => {
        loadData();
    }, [projectId]);

    const loadData = async () => {
        setLoading(true);
        setError(null);

        try {
            // Fetch project
            const projectRes = await fetch(`/api/scribe/projects/${projectId}`);
            if (!projectRes.ok) throw new Error("Failed to load project");
            const projectData = await projectRes.json();
            setProject({
                id: projectData.id,
                name: projectData.name,
                locale: projectData.locale || "en-US",
            });

            // Fetch SKUs
            const skusRes = await fetch(`/api/scribe/projects/${projectId}/skus`);
            if (!skusRes.ok) throw new Error("Failed to load SKUs");
            const skusData = await skusRes.json();
            setSkus(skusData);

            // Fetch variant attributes
            const attrsRes = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`);
            if (attrsRes.ok) {
                const attrsData = await attrsRes.json();
                setVariantAttributes(attrsData);
            }

            // Fetch topics for dirty-state checks
            const topicsRes = await fetch(`/api/scribe/projects/${projectId}/topics`);
            const topicsData = topicsRes.ok ? await topicsRes.json() : [];

            // Fetch generated content for all SKUs
            const contentMap: Record<string, GeneratedContent> = {};
            await Promise.all(
                skusData.map(async (sku: Sku) => {
                    try {
                        const contentRes = await fetch(
                            `/api/scribe/projects/${projectId}/generated-content/${sku.id}`
                        );
                        if (contentRes.ok) {
                            const content = await contentRes.json();
                            contentMap[sku.id] = content;
                        }
                    } catch (err) {
                        // SKU doesn't have content yet, that's OK
                    }
                })
            );

            setContentBySku(contentMap);
            setIsDirty(calculateDirtyState(skusData, topicsData, contentMap));

            // Expand first SKU if it has content
            if (skusData.length > 0 && contentMap[skusData[0].id]) {
                setExpandedSkus(new Set([skusData[0].id]));
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load data");
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateSample = async () => {
        if (skus.length === 0) {
            alert("Please add SKUs in Stage A before generating content");
            return;
        }

        // Validate topics before generation
        try {
            await validateTopics();
        } catch (err) {
            alert(err instanceof Error ? err.message : "Validation failed");
            return;
        }

        setGenerating(true);
        setGeneratingType('sample');
        setError(null);

        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/generate-copy`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: "sample", skuIds: [skus[0].id] }),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error?.message || "Failed to generate sample");
            }

            const { jobId } = await res.json();

            // Poll for job completion
            await pollJobStatus(jobId);

            // Reload content
            await loadData();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to generate sample");
        } finally {
            setGenerating(false);
            setGeneratingType(null);
        }
    };

    const handleGenerateAll = async (options?: { force?: boolean }) => {
        const force = options?.force ?? false;
        if (skus.length === 0) {
            alert("Please add SKUs in Stage A before generating content");
            return;
        }

        // Validate topics before generation
        try {
            await validateTopics();
        } catch (err) {
            alert(err instanceof Error ? err.message : "Validation failed");
            return;
        }

        setGenerating(true);
        setGeneratingType('all');
        setError(null);

        try {
            // Determine which SKUs to generate for:
            // - force=true (dirty state) → all SKUs
            // - default → only SKUs without content
            const targetSkuIds = force
                ? skus.map((sku) => sku.id)
                : skus.filter((sku) => !contentBySku[sku.id]).map((sku) => sku.id);

            if (targetSkuIds.length === 0) {
                alert("All SKUs already have generated content. Use Regenerate to recreate content for specific SKUs.");
                setGenerating(false);
                setGeneratingType(null);
                return;
            }

            const res = await fetch(`/api/scribe/projects/${projectId}/generate-copy`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: "all", skuIds: targetSkuIds }),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error?.message || "Failed to generate content");
            }

            const { jobId } = await res.json();

            // Poll for job completion
            await pollJobStatus(jobId);

            // Reload content
            await loadData();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to generate content");
        } finally {
            setGenerating(false);
            setGeneratingType(null);
        }
    };

    const validateTopics = async () => {
        const topicsRes = await fetch(`/api/scribe/projects/${projectId}/topics`);
        if (!topicsRes.ok) {
            throw new Error("Failed to load topics for validation");
        }

        const topics = await topicsRes.json();

        for (const sku of skus) {
            const skuTopics = topics.filter((t: any) => t.skuId === sku.id);
            const selectedCount = skuTopics.filter((t: any) => t.selected).length;
            if (selectedCount !== 5) {
                throw new Error(`Please select exactly 5 topics for each SKU in Stage B. SKU "${sku.skuCode}" has ${selectedCount} selected.`);
            }
        }
    };

    const handleRegenerateSku = async (skuId: string) => {
        setGenerating(true);
        setError(null);

        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/generate-copy`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mode: "all", skuIds: [skuId] }),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error?.message || "Failed to regenerate content");
            }

            const { jobId } = await res.json();

            // Poll for job completion
            await pollJobStatus(jobId);

            // Reload content
            await loadData();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to regenerate content");
        } finally {
            setGenerating(false);
        }
    };

    const pollJobStatus = async (jobId: string): Promise<void> => {
        return new Promise((resolve, reject) => {
            const interval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/scribe/jobs/${jobId}`);
                    if (!res.ok) {
                        clearInterval(interval);
                        reject(new Error("Failed to check job status"));
                        return;
                    }

                    const job = await res.json();

                    if (job.status === "succeeded") {
                        clearInterval(interval);
                        resolve();
                    } else if (job.status === "failed") {
                        clearInterval(interval);
                        reject(new Error(job.error_message || "Job failed"));
                    }
                } catch (err) {
                    clearInterval(interval);
                    reject(err);
                }
            }, 2000); // Poll every 2 seconds

            // Timeout after 5 minutes
            setTimeout(() => {
                clearInterval(interval);
                reject(new Error("Job timed out"));
            }, 300000);
        });
    };

    const handleToggleExpanded = (skuId: string) => {
        setExpandedSkus((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(skuId)) {
                newSet.delete(skuId);
            } else {
                newSet.add(skuId);
            }
            return newSet;
        });
    };

    const handleEditContent = (skuId: string) => {
        setEditingSkuId(skuId);
    };

    const handleSaveEdit = async (
        skuId: string,
        updates: { title: string; bullets: string[]; description: string }
    ) => {
        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/generated-content/${skuId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updates),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error?.message || "Failed to save changes");
            }

            // Reload content
            await loadData();
            setEditingSkuId(null);
        } catch (err) {
            alert(err instanceof Error ? err.message : "Failed to save changes");
        }
    };

    const handleExportCsv = async () => {
        setExporting(true);
        setError(null);

        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/export-copy`);
            if (!res.ok) {
                let message = "Failed to export CSV";
                try {
                    const body = await res.json();
                    message = body?.error?.message || message;
                } catch (_err) {
                    // ignore parse errors
                }
                throw new Error(message);
            }

            const blob = await res.blob();
            const disposition = res.headers.get("Content-Disposition");
            const filenameMatch = disposition?.match(/filename=\"?([^\";]+)\"?/);
            const filename = filenameMatch?.[1] || "scribe_export.csv";

            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to export CSV");
        } finally {
            setExporting(false);
        }
    };

    const calculateDirtyState = (
        skusData: Sku[],
        topicsData: any[],
        contentMap: Record<string, GeneratedContent>
    ) => {
        const hasAnyContent = Object.keys(contentMap).length > 0;
        if (!hasAnyContent) return false;

        const topicsLatestBySku: Record<string, number> = {};
        topicsData.forEach((topic: any) => {
            const topicTime = new Date(
                topic.updatedAt || topic.updated_at || topic.createdAt || topic.created_at || 0
            ).getTime();
            if (!topicsLatestBySku[topic.skuId] || topicTime > topicsLatestBySku[topic.skuId]) {
                topicsLatestBySku[topic.skuId] = topicTime;
            }
        });

        return skusData.some((sku) => {
            const content = contentMap[sku.id];
            if (!content) return false;

            const contentTime = new Date(
                content.updatedAt ||
                (content as any).updated_at ||
                (content as any).createdAt ||
                (content as any).created_at ||
                0
            ).getTime();
            const skuUpdateTime = new Date(
                (sku as any).updatedAt ||
                (sku as any).updated_at ||
                0
            ).getTime();
            const topicTime = topicsLatestBySku[sku.id] || 0;

            return (skuUpdateTime && skuUpdateTime > contentTime) || (topicTime && topicTime > contentTime);
        });
    };

    if (loading) {
        return (
            <div className="flex min-h-screen flex-col bg-slate-50">
                <ScribeHeader />
                <div className="flex flex-1 items-center justify-center">
                    <p className="text-slate-600">Loading...</p>
                </div>
            </div>
        );
    }

    if (error && Object.keys(contentBySku).length === 0) {
        return (
            <div className="flex min-h-screen flex-col bg-slate-50">
                <ScribeHeader />
                <div className="flex flex-1 items-center justify-center">
                    <p className="text-red-600">{error}</p>
                </div>
            </div>
        );
    }

    const hasContent = Object.keys(contentBySku).length > 0;
    const hasSample = skus.length > 0 && contentBySku[skus[0].id];

    return (
        <div className="flex min-h-screen flex-col bg-slate-50">
            <ScribeHeader />
            <ScribeProgressTracker
                currentStage="C"
                stageAComplete={skus.length > 0}
                stageBComplete={false}
                stageCComplete={hasContent}
                onNavigate={(stage) => {
                    if (stage === "A") router.push(`/scribe/${projectId}`);
                    if (stage === "B") router.push(`/scribe/${projectId}/stage-b`);
                }}
            />

            <div className="mx-auto w-full max-w-6xl px-6 py-8">
                {/* Page Heading */}
                <div className="mb-8">
                    <h1 className="text-2xl font-semibold text-slate-800">Amazon Content Creation</h1>
                    <p className="mt-1 text-sm text-slate-600">
                        Generate product titles, bullet points, descriptions, and backend keywords for Amazon listings.
                    </p>
                </div>

                {/* Generation Control Box */}
                <div className="mb-6 rounded-lg border border-slate-200 bg-white">
                    {/* Dirty State Warning */}
                    {isDirty && hasContent && (
                        <div className="border-b border-slate-200 p-4">
                            <DirtyStateWarning
                                message="Inputs or topics changed since content was generated"
                                onRegenerate={() => handleGenerateAll({ force: true })}
                                regenerating={generating}
                            />
                        </div>
                    )}

                    {/* Attribute Preferences Card */}
                    {variantAttributes.length > 0 && (
                        <AttributePreferencesCard
                            projectId={projectId}
                            skus={skus}
                            variantAttributes={variantAttributes}
                        />
                    )}

                    {/* Generation Buttons */}
                    <div className={variantAttributes.length > 0 ? "border-t border-slate-200 p-6" : "p-6"}>
                        <div className="flex items-center gap-4">
                            <button
                                onClick={handleGenerateSample}
                                disabled={generating || skus.length === 0}
                                className="rounded-lg bg-[#0a6fd6] px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {generatingType === 'sample' ? "Generating..." : hasSample ? "Regenerate Sample" : "Generate Sample (1 SKU)"}
                            </button>
                            <button
                                onClick={() => handleGenerateAll({ force: isDirty })}
                                disabled={generating || skus.length === 0}
                                className={`rounded-lg px-6 py-3 text-sm font-medium shadow-sm disabled:cursor-not-allowed disabled:opacity-50 ${hasSample
                                    ? "bg-[#0a6fd6] text-white hover:bg-[#0959ab]"
                                    : "border border-[#0a6fd6] bg-white text-[#0a6fd6] hover:bg-slate-50"
                                    }`}
                            >
                                {generatingType === 'all'
                                    ? "Generating..."
                                    : isDirty
                                        ? "Regenerate All"
                                        : `Generate All (${skus.length} SKUs)`}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
                        <p className="text-sm text-red-800">{error}</p>
                    </div>
                )}

                {/* Empty State - No Content Generated */}
                {!hasContent && (
                    <div className="rounded-lg border border-slate-200 bg-white p-12 text-center">
                        <h3 className="mb-2 text-lg font-semibold text-slate-800">
                            No Content Generated Yet
                        </h3>
                        <p className="text-sm text-slate-600">
                            Start by generating a sample for one SKU to preview the output,<br />
                            then generate for all SKUs when you're ready.
                        </p>
                    </div>
                )}

                {/* After Sample/Full Generation */}
                {hasContent && (
                    <>
                        {/* Generate All Button (shown after sample or full generation) */}
                        <div className="mb-6 flex items-center justify-between">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-800">Generated Content</h2>
                                <p className="text-sm text-slate-600">
                                    {Object.keys(contentBySku).length} of {skus.length} SKUs have generated content
                                </p>
                            </div>
                            {!generating && Object.keys(contentBySku).length < skus.length && (
                                <button
                                    onClick={() => handleGenerateAll()}
                                    className="rounded-lg bg-[#0a6fd6] px-6 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab]"
                                >
                                    Generate All
                                </button>
                            )}
                            {generating && (
                                <span className="text-sm text-slate-600">Generating...</span>
                            )}
                        </div>

                        {/* Amazon Product Cards */}
                        <div className="space-y-6">
                            {skus.map((sku, index) => {
                                const content = contentBySku[sku.id];
                                if (!content) return null;

                                return (
                                    <AmazonProductCard
                                        key={sku.id}
                                        sku={sku}
                                        content={content}
                                        isExpanded={expandedSkus.has(sku.id)}
                                        onToggleExpand={() => handleToggleExpanded(sku.id)}
                                        onEdit={() => handleEditContent(sku.id)}
                                        onRegenerate={() => handleRegenerateSku(sku.id)}
                                    />
                                );
                            })}
                        </div>

                        {/* Navigation Buttons */}
                        <div className="mt-8 flex items-center justify-between">
                            <button
                                onClick={() => router.push(`/scribe/${projectId}/stage-b`)}
                                className="rounded-lg border border-slate-300 bg-white px-6 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                            >
                                Previous
                            </button>
                            <button
                                onClick={handleExportCsv}
                                disabled={exporting}
                                className="rounded-lg bg-[#0a6fd6] px-6 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                                {exporting ? "Exporting..." : "Export CSV"}
                            </button>
                        </div>
                    </>
                )}
            </div>

            {/* Edit Panel */}
            {editingSkuId && contentBySku[editingSkuId] && (
                <EditGeneratedContentPanel
                    skuId={editingSkuId}
                    content={contentBySku[editingSkuId]}
                    onSave={handleSaveEdit}
                    onClose={() => setEditingSkuId(null)}
                />
            )}
        </div>
    );
}
