import type { ComposerProject, ProductBrief } from "../../../../../lib/composer/types";
import type {
  FaqFormItem,
  FaqItem,
  ProductInfoFormErrors,
  ProductInfoFormState,
  ProjectMetaPayload,
} from "./types";

export const MARKETPLACE_OPTIONS = ["US", "CA", "UK", "DE", "FR", "IT", "ES", "NL", "PL", "SE"];

const normalizeProductBrief = (brief?: ProductBrief): ProductBrief => ({
  targetAudience: brief?.targetAudience ?? "",
  useCases: brief?.useCases ?? "",
  differentiators: brief?.differentiators ?? "",
  safetyNotes: brief?.safetyNotes ?? "",
  certifications: brief?.certifications ?? "",
});

const trimOrNull = (value: string | null | undefined): string | null => {
  if (value == null) return null;
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
};

const cleanProductBrief = (brief: ProductBrief): ProductBrief => ({
  ...(brief.targetAudience?.trim()
    ? { targetAudience: brief.targetAudience.trim() }
    : {}),
  ...(brief.useCases?.trim() ? { useCases: brief.useCases.trim() } : {}),
  ...(brief.differentiators?.trim()
    ? { differentiators: brief.differentiators.trim() }
    : {}),
  ...(brief.safetyNotes?.trim() ? { safetyNotes: brief.safetyNotes.trim() } : {}),
  ...(brief.certifications?.trim() ? { certifications: brief.certifications.trim() } : {}),
});

const cleanFaqItems = (items: FaqFormItem[]): FaqItem[] => {
  return items
    .map((item) => ({
      question: item.question,
      answer: item.answer ?? "",
    }))
    .filter((item) => item.question.trim().length > 0)
    .map((item) => ({
      question: item.question.trim(),
      ...(item.answer?.trim() ? { answer: item.answer.trim() } : {}),
    }));
};

const createClientId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `faq-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export const buildFormStateFromProject = (project: ComposerProject): ProductInfoFormState => ({
  projectName: project.projectName ?? "",
  clientName: project.clientName ?? "",
  marketplaces: project.marketplaces ?? [],
  category: project.category ?? "",
  brandTone: project.brandTone ?? "",
  whatNotToSay: project.whatNotToSay ?? [],
  productBrief: normalizeProductBrief(project.productBrief as ProductBrief | undefined),
  suppliedInfoNotes:
    typeof project.suppliedInfo?.notes === "string" ? (project.suppliedInfo.notes as string) : "",
  faq: (project.faq ?? []).map((item) => ({
    clientId: createClientId(),
    question: item.question,
    answer: item.answer,
  })),
});

export const buildProjectMetaPayloadFromProject = (
  project: ComposerProject,
): ProjectMetaPayload => buildProjectMetaPayload(buildFormStateFromProject(project));

export const buildProjectMetaPayload = (state: ProductInfoFormState): ProjectMetaPayload => ({
  projectName: state.projectName.trim(),
  clientName: state.clientName.trim(),
  marketplaces: state.marketplaces,
  category: trimOrNull(state.category),
  brandTone: trimOrNull(state.brandTone),
  whatNotToSay: state.whatNotToSay.length ? state.whatNotToSay : null,
  productBrief: cleanProductBrief(state.productBrief),
  suppliedInfo: (() => {
    const trimmed = state.suppliedInfoNotes.trim();
    return trimmed ? { notes: trimmed } : {};
  })(),
  faq: (() => {
    const cleaned = cleanFaqItems(state.faq);
    return cleaned.length ? cleaned : null;
  })(),
});

export const validateProductInfoMeta = (state: ProductInfoFormState): ProductInfoFormErrors => {
  const errors: ProductInfoFormErrors = {};
  if (!state.projectName.trim()) {
    errors.projectName = "Project name is required";
  }
  if (!state.clientName.trim()) {
    errors.clientName = "Client name is required";
  }
  if (state.marketplaces.length === 0) {
    errors.marketplaces = "Select at least one marketplace";
  }
  return errors;
};
