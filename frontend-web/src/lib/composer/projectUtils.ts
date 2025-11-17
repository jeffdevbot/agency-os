import type { ProjectSummary } from "./projectSummary";

const STEP_LABELS: Record<string, string> = {
  product_info: "Product Info",
  keywords: "Keywords",
  keyword_upload: "Keyword Upload",
  keyword_cleanup: "Keyword Cleanup",
  keyword_grouping: "Grouping",
  themes: "Themes",
  sample: "Sample",
  bulk: "Bulk",
  backend_keywords: "Backend Keywords",
  strategy: "Strategy",
};

export const PROJECTS_PAGE_SIZE = 20;

export const formatStepLabel = (step: string | null): string => {
  if (!step) {
    return "Product Info";
  }
  return STEP_LABELS[step] ?? step.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
};

export const formatRelativeTime = (iso: string | null): string => {
  if (!iso) return "Unknown";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown";
  const now = Date.now();
  const diffMs = now - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 4) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  const years = Math.floor(days / 365);
  return `${years}y ago`;
};

export type ProjectWithDerived = ProjectSummary & {
  stepLabel: string;
  lastEditedLabel: string;
};

export const addProjectDerivedFields = (
  project: ProjectSummary,
): ProjectWithDerived => ({
  ...project,
  stepLabel: formatStepLabel(project.activeStep),
  lastEditedLabel: formatRelativeTime(project.lastEditedAt),
});
