"use client";

import { useState, useEffect } from "react";
import clsx from "clsx";

interface Topic {
  id: string;
  projectId: string;
  skuId: string;
  topicIndex: number;
  title: string;
  description: string | null;
  generatedBy: string | null;
  approved: boolean;
  approvedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

interface Sku {
  id: string;
  skuCode: string;
  productName: string | null;
}

interface StageBProps {
  projectId: string;
  skus: Sku[];
  projectStatus: string | null;
  onApprove: () => void;
  onUnapprove: () => void;
  approveLoading: boolean;
}

function normalizeStageStatus(status: string | null | undefined): string {
  const value = typeof status === "string" ? status.toLowerCase() : "draft";
  if (value === "stage_a_approved") return "stage_a_approved";
  if (value === "stage_b_approved") return "stage_b_approved";
  if (value === "stage_c_approved") return "stage_c_approved";
  if (value === "approved") return "approved";
  if (value === "archived") return "archived";
  return "draft";
}

export default function StageB({
  projectId,
  skus,
  projectStatus,
  onApprove,
  onUnapprove,
  approveLoading,
}: StageBProps) {
  const normalizedStatus = normalizeStageStatus(projectStatus);
  const [topics, setTopics] = useState<Record<string, Topic[]>>({});
  const [loading, setLoading] = useState(false);
  const [regeneratingSkus, setRegeneratingSkus] = useState<Set<string>>(new Set());
  const [generatingAll, setGeneratingAll] = useState(false);
  const isStageLocked =
    normalizedStatus === "stage_b_approved" ||
    normalizedStatus === "stage_c_approved" ||
    normalizedStatus === "approved";
  const canUnapproveB = normalizedStatus === "stage_b_approved";
  const isLockedByLaterStage = normalizedStatus === "stage_c_approved" || normalizedStatus === "approved";

  // Load topics for all SKUs
  useEffect(() => {
    const loadTopics = async () => {
      setLoading(true);
      try {
        const topicsBySku: Record<string, Topic[]> = {};

        for (const sku of skus) {
          const res = await fetch(`/api/scribe/projects/${projectId}/topics?skuId=${sku.id}`);
          if (res.ok) {
            const data = (await res.json()) as Topic[];
            topicsBySku[sku.id] = data;
          }
        }

        setTopics(topicsBySku);
      } catch (error) {
        console.error("Failed to load topics:", error);
      } finally {
        setLoading(false);
      }
    };

    if (skus.length > 0) {
      void loadTopics();
    }
  }, [projectId, skus]);

  const toggleTopicApproval = async (skuId: string, topicId: string, currentApproved: boolean) => {
    if (isStageLocked) return; // lock editing when Stage B (or later) is approved
    const skuTopics = topics[skuId] || [];
    const approvedCount = skuTopics.filter((t) => t.approved).length;

    // Prevent approving more than 5
    if (!currentApproved && approvedCount >= 5) {
      alert("You can only select up to 5 topics per SKU");
      return;
    }

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/topics/${topicId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved: !currentApproved }),
      });

      if (res.ok) {
        const updated = (await res.json()) as Topic;
        setTopics((prev) => ({
          ...prev,
          [skuId]: prev[skuId]?.map((t) => (t.id === topicId ? updated : t)) || [],
        }));
      }
    } catch (error) {
      console.error("Failed to update topic:", error);
    }
  };

  const handleRegenerate = async (skuId: string) => {
    setRegeneratingSkus((prev) => new Set(prev).add(skuId));

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/skus/${skuId}/regenerate-topics`, {
        method: "POST",
      });

      if (res.ok) {
        const { jobId } = (await res.json()) as { jobId: string };

        // Poll job status
        await pollJobStatus(jobId, skuId);
      }
    } catch (error) {
      console.error("Failed to regenerate topics:", error);
      setRegeneratingSkus((prev) => {
        const next = new Set(prev);
        next.delete(skuId);
        return next;
      });
    }
  };

  const pollJobStatus = async (jobId: string, skuId: string) => {
    const poll = async (): Promise<void> => {
      const res = await fetch(`/api/scribe/jobs/${jobId}`);
      if (!res.ok) return;

      const job = (await res.json()) as { status: string };

      if (job.status === "succeeded") {
        // Reload topics for this SKU
        const topicsRes = await fetch(`/api/scribe/projects/${projectId}/topics?skuId=${skuId}`);
        if (topicsRes.ok) {
          const data = (await topicsRes.json()) as Topic[];
          setTopics((prev) => ({ ...prev, [skuId]: data }));
        }
        setRegeneratingSkus((prev) => {
          const next = new Set(prev);
          next.delete(skuId);
          return next;
        });
      } else if (job.status === "failed") {
        alert("Topic generation failed. Please try again.");
        setRegeneratingSkus((prev) => {
          const next = new Set(prev);
          next.delete(skuId);
          return next;
        });
      } else if (job.status === "queued" || job.status === "running") {
        // Continue polling
        setTimeout(() => void poll(), 2000);
      }
    };

    await poll();
  };

  const handleGenerateAll = async () => {
    setGeneratingAll(true);

    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/generate-topics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}), // Empty body = all SKUs
      });

      if (res.ok) {
        const { jobId } = (await res.json()) as { jobId: string };

        // Poll job status for all SKUs
        await pollJobStatusForAll(jobId);
      } else {
        const errorBody = await res.json().catch(() => ({}));
        alert(`Failed to start topic generation: ${errorBody.error?.message || "Unknown error"}`);
        setGeneratingAll(false);
      }
    } catch (error) {
      console.error("Failed to generate all topics:", error);
      alert("Failed to start topic generation. Please try again.");
      setGeneratingAll(false);
    }
  };

  const pollJobStatusForAll = async (jobId: string) => {
    const poll = async (): Promise<void> => {
      const res = await fetch(`/api/scribe/jobs/${jobId}`);
      if (!res.ok) {
        setGeneratingAll(false);
        return;
      }

      const job = (await res.json()) as { status: string };

      if (job.status === "succeeded") {
        // Reload topics for all SKUs
        const topicsBySku: Record<string, Topic[]> = {};
        for (const sku of skus) {
          const topicsRes = await fetch(`/api/scribe/projects/${projectId}/topics?skuId=${sku.id}`);
          if (topicsRes.ok) {
            const data = (await topicsRes.json()) as Topic[];
            topicsBySku[sku.id] = data;
          }
        }
        setTopics(topicsBySku);
        setGeneratingAll(false);
      } else if (job.status === "failed") {
        alert("Topic generation failed for some SKUs. You can regenerate individual SKUs as needed.");
        setGeneratingAll(false);
      } else if (job.status === "queued" || job.status === "running") {
        // Continue polling
        setTimeout(() => void poll(), 2000);
      }
    };

    await poll();
  };

  // Check if all SKUs have exactly 5 approved topics
  const canApprove = skus.every((sku) => {
    const skuTopics = topics[sku.id] || [];
    const approvedCount = skuTopics.filter((t) => t.approved).length;
    return approvedCount === 5;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-slate-600">Loading topics...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Loading Banner */}
      {generatingAll && (
        <div className="rounded-2xl border-2 border-blue-300 bg-blue-50 p-4">
          <div className="flex items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent"></div>
            <p className="text-sm font-semibold text-blue-900">
              Generating topics for all SKUs... This may take up to a minute.
            </p>
          </div>
        </div>
      )}

      {/* Action Toolbar */}
      <div className="flex items-center justify-between gap-4">
        <button
          className="rounded-2xl bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={handleGenerateAll}
          disabled={generatingAll || regeneratingSkus.size > 0 || isStageLocked}
        >
          {generatingAll ? "Generating All..." : "Generate All Topics"}
        </button>

        <button
          className={clsx(
            "rounded-2xl px-6 py-3 text-sm font-semibold text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-50",
            canUnapproveB ? "bg-slate-600 hover:bg-slate-500" : "bg-emerald-600 hover:bg-emerald-500",
          )}
          onClick={canUnapproveB ? onUnapprove : onApprove}
          disabled={
            generatingAll ||
            approveLoading ||
            isLockedByLaterStage ||
            (!canUnapproveB && !canApprove)
          }
        >
          {approveLoading
            ? canUnapproveB
              ? "Unapproving..."
              : "Approving..."
            : canUnapproveB
              ? "Unapprove Stage B"
              : isLockedByLaterStage
                ? "Stage B Locked"
                : "Approve Stage B"}
        </button>
      </div>

      {skus.map((sku) => {
        const skuTopics = topics[sku.id] || [];
        const approvedCount = skuTopics.filter((t) => t.approved).length;
        const isRegenerating = regeneratingSkus.has(sku.id);

        return (
          <div key={sku.id} className="rounded-2xl border-2 border-slate-300 bg-white p-6 shadow-lg">
            {/* SKU Header */}
            <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  SKU: {sku.skuCode}
                </h3>
                {sku.productName && (
                  <p className="text-sm text-slate-600">{sku.productName}</p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={clsx(
                    "text-sm font-semibold",
                    approvedCount === 5 ? "text-emerald-600" : "text-slate-600"
                  )}
                >
                  Selected: {approvedCount} / 5 required
                </span>
                <button
                  className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => handleRegenerate(sku.id)}
                  disabled={isRegenerating || generatingAll || isStageLocked}
                >
                  {isRegenerating ? "Regenerating..." : "Regenerate"}
                </button>
              </div>
            </div>

            {/* Topics List */}
            {skuTopics.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-sm text-slate-600">No topics generated yet.</p>
                <button
                  className="mt-4 rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => handleRegenerate(sku.id)}
                  disabled={isRegenerating || generatingAll || isStageLocked}
                >
                  {isRegenerating ? "Regenerating..." : "Generate Topics"}
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {skuTopics.map((topic) => (
                  <div
                    key={topic.id}
                    className={clsx(
                      "rounded-lg border p-4 transition-all",
                      topic.approved
                        ? "border-emerald-300 bg-emerald-50"
                        : "border-slate-200 bg-white hover:border-slate-300",
                      isStageLocked && "cursor-not-allowed opacity-50"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={topic.approved}
                        onChange={() => {
                          if (isStageLocked) return;
                          void toggleTopicApproval(sku.id, topic.id, topic.approved);
                        }}
                        className="mt-1 h-5 w-5 cursor-pointer rounded border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500"
                        disabled={isStageLocked}
                      />
                      <div className="flex-1">
                        <h4 className="font-semibold text-slate-900">{topic.title}</h4>
                        {topic.description && (
                          <div className="mt-1 text-sm text-slate-600">
                            {topic.description.includes("\n") ? (
                              <ul className="list-disc pl-4">
                                {topic.description.split("\n").map((line, idx) => (
                                  <li key={idx}>{line.replace(/^•\s*/, "")}</li>
                                ))}
                              </ul>
                            ) : (
                              <p>{topic.description}</p>
                            )}
                          </div>
                        )}
                      </div>
                      <span className="text-xs text-slate-500">#{topic.topicIndex}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

    </div>
  );
}
