"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ProductInfoStep } from "../components/product-info/ProductInfoStep";
import { ContentStrategyStep } from "../components/content-strategy/ContentStrategyStep";
import { useComposerProject } from "@/lib/composer/hooks/useComposerProject";
import { useProjectAutosave } from "@/lib/composer/hooks/useProjectAutosave";
import { useSkuVariants } from "@/lib/composer/hooks/useSkuVariants";
import { validateProductInfoForm } from "@/lib/composer/productInfo/validateProductInfoForm";
import type { StrategyType } from "@agency/lib/composer/types";
import {
  COMPOSER_STEPS,
  DEFAULT_STEP_ID,
  getNextStepId,
  getPreviousStepId,
  isComposerStepId,
  type ComposerStepId,
} from "@/lib/composer/steps";

const AutosaveStatusBadge = ({ status }: { status: string }) => {
  const colorMap: Record<string, string> = {
    idle: "text-[#475569]",
    saving: "text-[#92400e]",
    saved: "text-[#15803d]",
    error: "text-[#b91c1c]",
  };
  const labelMap: Record<string, string> = {
    idle: "Idle",
    saving: "Saving…",
    saved: "Saved",
    error: "Autosave failed",
  };
  return (
    <span className={`text-xs font-semibold ${colorMap[status] ?? "text-[#475569]"}`}>
      {labelMap[status] ?? status}
    </span>
  );
};

const PlaceholderCard = ({ title, description }: { title: string; description: string }) => (
  <div className="rounded-3xl border border-dashed border-[#cbd5f5] bg-white/80 p-10 text-center shadow-inner">
    <p className="text-lg font-semibold text-[#0f172a]">{title}</p>
    <p className="mt-2 text-sm text-[#475569]">{description}</p>
  </div>
);

export default function ComposerWizardStepPage() {
  const params = useParams<{ projectId?: string | string[]; stepId?: string | string[] }>();
  const router = useRouter();
  const projectId = Array.isArray(params.projectId)
    ? params.projectId[0]
    : params.projectId ?? undefined;
  const requestedStep = Array.isArray(params.stepId) ? params.stepId[0] : params.stepId;
  const { project, setProject, isLoading, isError, errorMessage } = useComposerProject(projectId);
  const {
    variants,
    setVariants,
    isLoading: variantsLoading,
    error: variantsError,
    refresh: refreshVariants,
    saveVariants,
    deleteVariant,
    isSaving: variantsSaving,
  } = useSkuVariants(projectId);

  const validStep: ComposerStepId = useMemo(() => {
    if (isComposerStepId(requestedStep)) {
      return requestedStep;
    }
    return DEFAULT_STEP_ID;
  }, [requestedStep]);

  useEffect(() => {
    if (!isComposerStepId(requestedStep)) {
      router.replace(`/composer/${projectId}/${DEFAULT_STEP_ID}`);
    }
  }, [projectId, requestedStep, router]);

  const { savePartial, autosaveStatus } = useProjectAutosave(projectId, {
    onSaved: (updatedProject) => setProject(updatedProject),
  });

  const navigateToStep = (stepId: ComposerStepId) => {
    if (!project) return;
    if (project.activeStep !== stepId) {
      setProject({ ...project, activeStep: stepId });
      savePartial({ activeStep: stepId });
    }
    router.push(`/composer/${project.id}/${stepId}`);
  };

  const previousStepId = getPreviousStepId(validStep);
  const nextStepId = getNextStepId(validStep);

  // Validate product info step
  const productInfoValidation = useMemo(() => {
    if (validStep !== "product_info") {
      return { isValid: true, errors: {} };
    }
    return validateProductInfoForm(project, variants);
  }, [validStep, project, variants]);

  // Validate content strategy step
  const contentStrategyValidation = useMemo(() => {
    if (validStep !== "content_strategy") {
      return { isValid: true };
    }
    // Strategy must be selected
    if (!project?.strategyType) {
      return { isValid: false };
    }
    return { isValid: true };
  }, [validStep, project?.strategyType]);

  // Determine if Next button should be disabled
  const isNextDisabled = useMemo(() => {
    if (!nextStepId) return true;
    if (validStep === "product_info" && !productInfoValidation.isValid) {
      return true;
    }
    if (validStep === "content_strategy" && !contentStrategyValidation.isValid) {
      return true;
    }
    return false;
  }, [nextStepId, validStep, productInfoValidation.isValid, contentStrategyValidation.isValid]);

  const statusLabel = project?.status ?? "Draft";
  const marketplaces = project?.marketplaces ?? [];

  const renderStepContent = () => {
    if (!project) return null;
    switch (validStep) {
      case "product_info":
        return (
          <ProductInfoStep
            projectId={project.id}
            project={project}
            onSaveMeta={savePartial}
            variants={variants}
            setVariants={setVariants}
            variantsLoading={variantsLoading}
            variantsError={variantsError}
            variantsSaving={variantsSaving}
            saveVariants={saveVariants}
            deleteVariant={deleteVariant}
          />
        );
      case "content_strategy":
        return (
          <ContentStrategyStep
            project={project}
            variants={variants}
            onSaveStrategy={(strategyType: StrategyType) => {
              setProject({ ...project, strategyType });
              savePartial({ strategyType });
            }}
            onVariantsChange={() => {
              // Refresh variants to get updated groupId assignments
              void refreshVariants();
            }}
            onHighlightAttributesChange={(attributes) => {
              setProject({ ...project, highlightAttributes: attributes });
              savePartial({ highlightAttributes: attributes });
            }}
          />
        );
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f1f5f9] text-sm text-[#475569]">
        Loading project…
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#f1f5f9] px-6 text-center text-[#475569]">
        <p className="text-2xl font-semibold text-[#0f172a]">Unable to load project</p>
        <p className="mt-2 text-sm">{errorMessage ?? "This project could not be found."}</p>
        <Link
          href="/composer"
          className="mt-6 rounded-full bg-[#0a6fd6] px-5 py-2 text-sm font-semibold text-white shadow"
        >
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#eef2ff] via-[#f8fbff] to-[#ecf4ff] p-6">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <header className="rounded-3xl bg-white/95 p-6 shadow">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.4em] text-[#94a3b8]">
                Composer Project
              </p>
              <h1 className="text-3xl font-semibold text-[#0f172a]">{project.projectName}</h1>
              <p className="text-sm text-[#64748b]">
                {project.clientName ?? "No client"}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {marketplaces.length ? (
                  marketplaces.map((marketplace) => (
                    <span
                      key={marketplace}
                      className="rounded-full bg-[#eef2ff] px-2 py-0.5 text-xs text-[#4338ca]"
                    >
                      {marketplace}
                    </span>
                  ))
                ) : (
                  <span className="rounded-full bg-[#e2e8f0] px-2 py-0.5 text-xs text-[#475569]">
                    No marketplaces
                  </span>
                )}
              </div>
            </div>
            <div className="text-right">
              <span className="rounded-full bg-[#e0f2fe] px-4 py-1 text-xs font-semibold text-[#0369a1]">
                {statusLabel}
              </span>
              <div className="mt-1">
                <AutosaveStatusBadge status={autosaveStatus} />
              </div>
            </div>
          </div>
        </header>

        <nav className="rounded-3xl bg-white/95 p-4 shadow">
          <ol className="flex flex-wrap gap-2">
            {COMPOSER_STEPS.map((step, index) => {
              const isActive = step.id === validStep;
              return (
                <li key={step.id}>
                  <button
                    onClick={() => navigateToStep(step.id)}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                      isActive
                        ? "bg-[#0a6fd6] text-white shadow"
                        : "bg-[#eef2ff] text-[#475569] hover:-translate-y-0.5 hover:bg-white"
                    }`}
                  >
                    <span
                      className={`mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold ${
                        isActive
                          ? "bg-white/25 text-white"
                          : "bg-white text-[#0f172a]"
                      }`}
                    >
                      {index + 1}
                    </span>
                    {step.label}
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <main className="rounded-3xl bg-white/95 p-6 shadow">
          {renderStepContent()}
          <div className="mt-8 flex items-center justify-between">
            <button
              onClick={() => previousStepId && navigateToStep(previousStepId)}
              disabled={!previousStepId}
              className="rounded-full px-5 py-2 text-sm font-semibold text-[#475569] disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => nextStepId && navigateToStep(nextStepId)}
              disabled={isNextDisabled}
              className="rounded-full bg-[#0a6fd6] px-5 py-2 text-sm font-semibold text-white shadow disabled:opacity-40"
              title={
                validStep === "product_info" && !productInfoValidation.isValid
                  ? "Complete required fields to continue"
                  : undefined
              }
            >
              Next
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}
