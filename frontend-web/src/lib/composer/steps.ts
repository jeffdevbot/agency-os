export const COMPOSER_STEPS = [
  { id: "product_info", label: "Product Info" },
  { id: "content_strategy", label: "Content Strategy" },
  { id: "keyword_upload", label: "Keyword Upload" },
  { id: "keyword_cleanup", label: "Keyword Cleanup" },
] as const;

export type ComposerStepId = (typeof COMPOSER_STEPS)[number]["id"];

export const DEFAULT_STEP_ID: ComposerStepId = "product_info";

export const isComposerStepId = (value: string | null | undefined): value is ComposerStepId =>
  COMPOSER_STEPS.some((step) => step.id === value);

export const getStepLabel = (stepId: ComposerStepId): string =>
  COMPOSER_STEPS.find((step) => step.id === stepId)?.label ?? stepId;

export const getStepIndex = (stepId: ComposerStepId): number =>
  COMPOSER_STEPS.findIndex((step) => step.id === stepId);

export const getNextStepId = (stepId: ComposerStepId): ComposerStepId | null => {
  const idx = getStepIndex(stepId);
  if (idx === -1 || idx + 1 >= COMPOSER_STEPS.length) {
    return null;
  }
  return COMPOSER_STEPS[idx + 1].id;
};

export const getPreviousStepId = (stepId: ComposerStepId): ComposerStepId | null => {
  const idx = getStepIndex(stepId);
  if (idx <= 0) {
    return null;
  }
  return COMPOSER_STEPS[idx - 1].id;
};
