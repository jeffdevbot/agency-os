"use client";

import { useState } from "react";
import clsx from "clsx";

type ScribeProjectStatus =
  | "draft"
  | "stage_a_approved"
  | "stage_b_approved"
  | "stage_c_approved"
  | "approved"
  | "archived";

interface ProgressStepperProps {
  projectStatus: ScribeProjectStatus | null;
  lastUpdated?: string;
  onStageClick?: (stageId: "stage_a" | "stage_b" | "stage_c") => void;
}

interface StepConfig {
  id: string;
  label: string;
  sublabel: string;
}

const STEPS: StepConfig[] = [
  {
    id: "stage_a",
    label: "Stage A — Product Data",
    sublabel: "Add product details & guidance",
  },
  {
    id: "stage_b",
    label: "Stage B — Topic Ideas",
    sublabel: "Shape the angles we'll write to",
  },
  {
    id: "stage_c",
    label: "Stage C — Listing Copy",
    sublabel: "Generate optimized titles & bullets",
  },
];

type StepState = "completed" | "active" | "locked";

function getStepState(stepId: string, status: ScribeProjectStatus | null): StepState {
  const effectiveStatus = (status ?? "draft").toLowerCase() as ScribeProjectStatus;

  if (effectiveStatus === "archived") {
    return "locked";
  }

  if (stepId === "stage_a") {
    if (effectiveStatus === "draft") return "active";
    return "completed";
  }

  if (stepId === "stage_b") {
    if (effectiveStatus === "draft") return "locked";
    if (effectiveStatus === "stage_a_approved") return "active";
    return "completed";
  }

  if (stepId === "stage_c") {
    if (effectiveStatus === "draft" || effectiveStatus === "stage_a_approved") return "locked";
    if (effectiveStatus === "stage_b_approved") return "active";
    return "completed";
  }

  return "locked";
}

function getLockedTooltip(stepId: string): string {
  if (stepId === "stage_b") return "Finish Stage A first";
  if (stepId === "stage_c") return "Finish Stage B first";
  return "";
}

function formatRelativeTime(dateString: string | undefined): string {
  if (!dateString) return "";

  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hr${diffHours > 1 ? "s" : ""} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;

    return date.toLocaleDateString();
  } catch {
    return "";
  }
}

function formatStatusLabel(status: ScribeProjectStatus | null): string {
  if (!status || status === "draft") return "Draft";
  if (status === "stage_a_approved") return "Stage A Approved";
  if (status === "stage_b_approved") return "Stage B Approved";
  if (status === "stage_c_approved") return "Stage C Approved";
  if (status === "approved") return "Approved";
  if (status === "archived") return "Archived";
  return "Draft";
}

export default function ProgressStepper({
  projectStatus,
  lastUpdated,
  onStageClick,
}: ProgressStepperProps) {
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);

  const handleStepClick = (stepId: string, state: StepState) => {
    if (state === "locked") {
      // Don't navigate; tooltip will show on hover
      return;
    }

    // Call the parent's click handler
    if (onStageClick && (stepId === "stage_a" || stepId === "stage_b" || stepId === "stage_c")) {
      onStageClick(stepId);
    }
  };

  const relativeTime = formatRelativeTime(lastUpdated);

  return (
    <div className="mb-6 rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Header Band: SCRIBE branding + tagline on left, status on right */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-700 md:text-sm">
            Scribe
          </h2>
          <p className="text-sm text-slate-600 md:text-base">
            Turn messy briefs into Amazon-ready copy in 3 quick steps.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {relativeTime && (
            <span className="text-xs text-slate-400">Last updated: {relativeTime}</span>
          )}
          <span
            className={clsx(
              "rounded-full px-3 py-1 text-xs font-semibold",
              projectStatus === "archived"
                ? "bg-slate-100 text-slate-600"
                : projectStatus === "stage_a_approved"
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-blue-100 text-blue-700"
            )}
          >
            {formatStatusLabel(projectStatus)}
          </span>
        </div>
      </div>

      {/* Stepper Band */}
      <div className="px-6 py-5">
        <nav
          className="flex items-start justify-between gap-4"
          aria-label="Project stages"
        >
          {STEPS.map((step, index) => {
            const state = getStepState(step.id, projectStatus);
            const isLocked = state === "locked";
            const isActive = state === "active";
            const isCompleted = state === "completed";
            const showTooltip = isLocked && hoveredStep === step.id;

            return (
              <div key={step.id} className="relative flex flex-1 items-start gap-3">
                {/* Connector Line */}
                {index < STEPS.length - 1 && (
                  <div className="absolute left-[20px] top-[20px] h-[2px] w-[calc(100%+1rem)]">
                    <div
                      className={clsx(
                        "h-full transition-colors duration-300",
                        isCompleted ? "bg-emerald-400" : "bg-slate-200"
                      )}
                    />
                  </div>
                )}

                {/* Step Content */}
                <button
                  type="button"
                  className={clsx(
                    "relative flex flex-1 items-start gap-3 text-left transition-opacity",
                    isLocked ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:opacity-80"
                  )}
                  onClick={() => handleStepClick(step.id, state)}
                  onMouseEnter={() => setHoveredStep(step.id)}
                  onMouseLeave={() => setHoveredStep(null)}
                  aria-label={`${step.label} (${state})`}
                  aria-disabled={isLocked}
                >
                  {/* Dot/Icon */}
                  <div className="relative z-10 flex-shrink-0">
                    <div
                      className={clsx(
                        "flex h-10 w-10 items-center justify-center rounded-full transition-all duration-300",
                        isCompleted
                          ? "bg-emerald-500 text-white shadow-lg"
                          : isActive
                            ? "animate-pulse bg-[#0a6fd6] text-white shadow-lg"
                            : "border-2 border-slate-300 bg-white text-slate-400"
                      )}
                    >
                      {isCompleted ? (
                        <svg
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={3}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      ) : isActive ? (
                        <div className="h-3 w-3 rounded-full bg-white" />
                      ) : (
                        <div className="h-3 w-3 rounded-full bg-slate-300" />
                      )}
                    </div>
                  </div>

                  {/* Label & Sublabel */}
                  <div className="flex flex-col gap-1 pt-1">
                    <span
                      className={clsx(
                        "text-sm font-semibold uppercase tracking-wide",
                        isCompleted
                          ? "text-emerald-700"
                          : isActive
                            ? "text-[#0a6fd6]"
                            : "text-slate-500"
                      )}
                    >
                      {step.label}
                    </span>
                    <span className="text-xs text-slate-600">{step.sublabel}</span>
                  </div>

                  {/* Tooltip for Locked Steps */}
                  {showTooltip && (
                    <div className="absolute left-0 top-full z-20 mt-2 whitespace-nowrap rounded-lg bg-slate-900 px-3 py-2 text-xs text-white shadow-lg">
                      {getLockedTooltip(step.id)}
                      <div className="absolute -top-1 left-6 h-2 w-2 rotate-45 bg-slate-900" />
                    </div>
                  )}
                </button>
              </div>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
