"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ScribeHeader } from "../../components/ScribeHeader";
import { ScribeProgressTracker } from "../../components/ScribeProgressTracker";
import { DirtyStateWarning } from "./DirtyStateWarning";
import { SkuTopicsCard } from "./SkuTopicsCard";

interface Project {
    id: string;
    name: string;
}

interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
    updatedAt: string;
}

interface Topic {
    id: string;
    skuId: string;
    topicIndex: number;
    title: string;
    description: string | null;
    selected: boolean;
}

export function StageB() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.projectId as string;

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [project, setProject] = useState<Project | null>(null);
    const [skus, setSkus] = useState<Sku[]>([]);
    const [topicsBySku, setTopicsBySku] = useState<Record<string, Topic[]>>({});
    const [generating, setGenerating] = useState(false);
    const [isDirty, setIsDirty] = useState(false);

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
            setProject(projectData);

            // Fetch SKUs
            const skusRes = await fetch(`/api/scribe/projects/${projectId}/skus`);
            if (!skusRes.ok) throw new Error("Failed to load SKUs");
            const skusData = await skusRes.json();
            setSkus(skusData);

            // Fetch topics
            const topicsRes = await fetch(`/api/scribe/projects/${projectId}/topics`);
            if (topicsRes.ok) {
                const topicsData = await topicsRes.json();
                console.log("📊 Loaded topics from API:", topicsData.map((t: any) => ({
                    id: t.id,
                    skuId: t.skuId,
                    title: t.title,
                    selected: t.selected
                })));

                // Group topics by SKU
                const grouped: Record<string, Topic[]> = {};
                topicsData.forEach((topic: any) => {
                    if (!grouped[topic.skuId]) grouped[topic.skuId] = [];
                    grouped[topic.skuId].push({
                        id: topic.id,
                        skuId: topic.skuId,
                        topicIndex: topic.topicIndex,
                        title: topic.title,
                        description: topic.description,
                        selected: topic.selected ?? false,
                    });
                });

                // Sort topics by index
                Object.keys(grouped).forEach((skuId) => {
                    grouped[skuId].sort((a, b) => a.topicIndex - b.topicIndex);
                });

                console.log("📦 Grouped topics by SKU:", Object.fromEntries(
                    Object.entries(grouped).map(([skuId, topics]) => [
                        skuId,
                        topics.map(t => ({ id: t.id, selected: t.selected, title: t.title }))
                    ])
                ));

                setTopicsBySku(grouped);

                // Check dirty state
                checkDirtyState(skusData, topicsData);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load data");
        } finally {
            setLoading(false);
        }
    };

    const checkDirtyState = (skusData: Sku[], topicsData: any[]) => {
        // Check if any SKU was updated after topics were generated
        if (topicsData.length === 0) {
            setIsDirty(false);
            return;
        }

        // Get the most recent topic creation time
        const latestTopicTime = topicsData.reduce((latest, topic) => {
            const topicTime = new Date(topic.createdAt).getTime();
            return Math.max(latest, topicTime);
        }, 0);

        // Check if any SKU was updated after that
        const hasNewerSku = skusData.some((sku) => {
            const skuUpdateTime = new Date(sku.updatedAt).getTime();
            return skuUpdateTime > latestTopicTime;
        });

        setIsDirty(hasNewerSku);
    };

    const handleGenerateTopics = async () => {
        if (skus.length === 0) {
            alert("Please add SKUs in Stage A before generating topics");
            return;
        }

        setGenerating(true);
        setError(null);

        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/generate-topics`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}), // Empty body generates for all SKUs
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error?.message || "Failed to generate topics");
            }

            const { jobId } = await res.json();

            // Poll for job completion (simple polling)
            await pollJobStatus(jobId);

            // Reload topics
            await loadData();

            setIsDirty(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to generate topics");
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

    const handleToggleTopic = async (skuId: string, topicId: string) => {
        // First, get current state to calculate newSelected BEFORE setState
        const skuTopics = topicsBySku[skuId] || [];
        const topic = skuTopics.find((t) => t.id === topicId);
        const selectedCount = skuTopics.filter((t) => t.selected).length;

        if (!topic) {
            console.error("❌ Topic not found:", topicId);
            return;
        }

        // Don't allow selecting more than 5
        if (!topic.selected && selectedCount >= 5) {
            alert("You can only select up to 5 topics per SKU");
            return;
        }

        const newSelected = !topic.selected;
        console.log("🔍 Toggle Debug:", {
            skuId,
            topicId,
            currentSelected: topic.selected,
            newSelected,
            selectedCount,
        });

        // Optimistic update
        setTopicsBySku((prev) => ({
            ...prev,
            [skuId]: prev[skuId].map((t) =>
                t.id === topicId ? { ...t, selected: newSelected } : t
            ),
        }));

        // Save to backend
        console.log("📤 Sending PATCH with selected:", newSelected);
        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/topics/${topicId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ selected: newSelected }),
            });

            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error?.message || "Failed to save topic selection");
            }

            const responseData = await res.json();
            console.log("📥 PATCH response:", responseData);
        } catch (err) {
            console.error("❌ PATCH error:", err);
            // Revert optimistic update on error
            setTopicsBySku((prev) => ({
                ...prev,
                [skuId]: prev[skuId].map((t) =>
                    t.id === topicId ? { ...t, selected: !newSelected } : t
                ),
            }));
            setError(err instanceof Error ? err.message : "Failed to save topic selection");
        }
    };

    const handleNext = () => {
        // Check if all SKUs have 5 topics selected
        const allSkusReady = skus.every((sku) => {
            const topics = topicsBySku[sku.id] || [];
            const selectedCount = topics.filter((t) => t.selected).length;
            return selectedCount === 5;
        });

        if (!allSkusReady) {
            alert("Please select exactly 5 topics for each SKU before proceeding");
            return;
        }

        router.push(`/scribe/${projectId}/stage-c`);
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

    if (error && !topicsBySku) {
        return (
            <div className="flex min-h-screen flex-col bg-slate-50">
                <ScribeHeader />
                <div className="flex flex-1 items-center justify-center">
                    <p className="text-red-600">{error}</p>
                </div>
            </div>
        );
    }

    const hasTopics = Object.keys(topicsBySku).length > 0;
    const allSkusHaveTopics = skus.every((sku) => topicsBySku[sku.id]?.length > 0);

    return (
        <div className="flex min-h-screen flex-col bg-slate-50">
            <ScribeHeader />
            <ScribeProgressTracker
                currentStage="B"
                stageAComplete={skus.length > 0}
                stageBComplete={false}
                stageCComplete={false}
                onNavigate={(stage) => {
                    if (stage === "A") router.push(`/scribe/${projectId}`);
                    if (stage === "C") router.push(`/scribe/${projectId}/stage-c`);
                }}
            />

            <div className="mx-auto w-full max-w-6xl px-6 py-8">
                {/* Dirty State Warning */}
                {isDirty && hasTopics && (
                    <DirtyStateWarning
                        message="Stage A data has changed since topics were generated"
                        onRegenerate={handleGenerateTopics}
                        regenerating={generating}
                    />
                )}

                {/* Error Message */}
                {error && (
                    <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
                        <p className="text-sm text-red-800">{error}</p>
                    </div>
                )}

                {/* Empty State - No Topics Generated */}
                {!hasTopics && (
                    <div className="flex flex-col items-center justify-center py-16">
                        <h2 className="mb-2 text-2xl font-semibold text-slate-800">
                            Generate Topics
                        </h2>
                        <p className="mb-6 text-center text-slate-600">
                            Generate up to 8 topic ideas for each SKU based on your inputs from Stage A
                        </p>
                        <button
                            onClick={handleGenerateTopics}
                            disabled={generating || skus.length === 0}
                            className="rounded-lg bg-[#0a6fd6] px-6 py-3 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {generating ? "Generating..." : "Generate Topics"}
                        </button>
                        {skus.length === 0 && (
                            <p className="mt-4 text-sm text-red-600">
                                Please add SKUs in Stage A before generating topics
                            </p>
                        )}
                    </div>
                )}

                {/* Topics Display */}
                {hasTopics && (
                    <>
                        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
                            <h2 className="mb-2 text-lg font-semibold text-slate-800">
                                Select Topics
                            </h2>
                            <p className="text-sm text-slate-600">
                                Select exactly 5 topics for each SKU. Not happy with the results? Go back to Stage A to refine your inputs—topics are heavily influenced by the questions you provide. Edit your data, return here, and regenerate for different results.
                            </p>
                        </div>

                        <div className="space-y-6">
                            {skus.map((sku) => (
                                <SkuTopicsCard
                                    key={sku.id}
                                    sku={sku}
                                    topics={topicsBySku[sku.id] || []}
                                    onToggleTopic={(topicId) => handleToggleTopic(sku.id, topicId)}
                                />
                            ))}
                        </div>

                        {/* Navigation Buttons */}
                        <div className="mt-8 flex items-center justify-between">
                            <button
                                onClick={() => router.push(`/scribe/${projectId}`)}
                                className="rounded-lg border border-slate-300 bg-white px-6 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                            >
                                Previous
                            </button>
                            <button
                                onClick={handleNext}
                                className="rounded-lg bg-[#0a6fd6] px-6 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab]"
                            >
                                Next
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
