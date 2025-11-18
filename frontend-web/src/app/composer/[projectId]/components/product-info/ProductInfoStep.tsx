"use client";

import { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComposerProject, ComposerSkuVariant } from "@agency/lib/composer/types";
import type {
  ProjectMetaPayload,
  ProductInfoFormState,
  ProductInfoFormErrors,
} from "@/lib/composer/productInfo/types";
import {
  MARKETPLACE_OPTIONS,
  buildFormStateFromProject,
  buildProjectMetaPayload,
  buildProjectMetaPayloadFromProject,
  validateProductInfoMeta,
} from "@/lib/composer/productInfo/state";
import { useSkuVariants } from "@/lib/composer/hooks/useSkuVariants";
import type { SkuVariantInput } from "@/lib/composer/hooks/useSkuVariants";
import { inferAttributes } from "@/lib/composer/productInfo/inferAttributes";
import { ProjectMetaForm } from "./ProjectMetaForm";
import { BrandGuidelinesForm } from "./BrandGuidelinesForm";
import { ProductBriefForm } from "./ProductBriefForm";
import { FaqRepeater } from "./FaqRepeater";
import { SkuTable } from "./SkuTable";
import { AttributeSummaryPanel } from "./AttributeSummaryPanel";

interface ProductInfoStepProps {
  project: ComposerProject;
  projectId: string;
  onSaveMeta: (payload: ProjectMetaPayload) => void;
}

const prepareVariantPayloads = (variants: ComposerSkuVariant[]) => {
  const payload: SkuVariantInput[] = [];
  let hasInvalidRow = false;
  variants.forEach((variant) => {
    const sku = variant.sku?.trim() ?? "";
    const asin = variant.asin?.trim() ?? "";
    const parentSku = variant.parentSku?.trim() || null;
    const notes = variant.notes?.trim() || null;
    const attributes = Object.entries(variant.attributes ?? {}).reduce<
      Record<string, string | null>
    >((acc, [key, value]) => {
      if (!key) return acc;
      const trimmedKey = key.trim();
      if (!trimmedKey) return acc;
      if (typeof value === "string") {
        const trimmed = value.trim();
        acc[trimmedKey] = trimmed.length ? trimmed : null;
      } else {
        acc[trimmedKey] = value ?? null;
      }
      return acc;
    }, {});
    const hasAttributeData = Object.values(attributes).some(
      (value) => (value ?? "").toString().trim().length > 0,
    );
    const hasContent = sku || asin || parentSku || notes || hasAttributeData;
    if (!hasContent) {
      return;
    }
    if (!sku) {
      hasInvalidRow = true;
      return;
    }
    payload.push({
      id: variant.id && variant.id.startsWith("temp-") ? undefined : variant.id,
      sku,
      asin: asin || null,
      parentSku,
      attributes,
      notes,
    });
  });
  const comparisonSignature = payload.map(({ sku, asin, parentSku, attributes, notes }) => ({
    sku,
    asin,
    parentSku,
    attributes,
    notes,
  }));
  return { payload, comparisonSignature, hasInvalidRow };
};

export const ProductInfoStep = ({ project, projectId, onSaveMeta }: ProductInfoStepProps) => {
  const [formState, setFormState] = useState<ProductInfoFormState>(() =>
    buildFormStateFromProject(project),
  );
  const [errors, setErrors] = useState<ProductInfoFormErrors>(() =>
    validateProductInfoMeta(formState),
  );
  const skipSaveRef = useRef(true);
  const lastSavedPayloadRef = useRef<string | null>(null);
  const lastPayloadRef = useRef<string | null>(null);
  const lastProjectSignatureRef = useRef<string | null>(null);
  const {
    variants,
    setVariants,
    isLoading: variantsLoading,
    error: variantsError,
    saveVariants,
    deleteVariant,
    isSaving: variantsSaving,
  } = useSkuVariants(projectId);
  const attributeSummary = useMemo(() => inferAttributes(variants), [variants]);
  const variantInitialSyncRef = useRef(true);
  const lastVariantSentSignatureRef = useRef<string | null>(null);

  const syncIncomingProjectState = useCallback(() => {
    const signature = `${project.id}:${project.lastSavedAt ?? ""}`;
    const serverPayload = JSON.stringify(buildProjectMetaPayloadFromProject(project));
    const previousProjectId = lastProjectSignatureRef.current?.split(":")[0];

    const applySnapshot = () => {
      const nextState = buildFormStateFromProject(project);
      const validation = validateProductInfoMeta(nextState);
      return { nextState, validation };
    };

    if (project.id !== previousProjectId) {
      skipSaveRef.current = true;
      lastProjectSignatureRef.current = signature;
      lastPayloadRef.current = serverPayload;
      lastSavedPayloadRef.current = serverPayload;
      return applySnapshot();
    }

    if (lastProjectSignatureRef.current === signature) {
      return null;
    }

    lastProjectSignatureRef.current = signature;

    if (lastSavedPayloadRef.current && lastSavedPayloadRef.current === serverPayload) {
      return null;
    }

    skipSaveRef.current = true;
    lastPayloadRef.current = serverPayload;
    return applySnapshot();
  }, [project]);

  useEffect(() => {
    const syncResult = syncIncomingProjectState();
    if (!syncResult) return;
    startTransition(() => {
      setFormState(syncResult.nextState);
      setErrors(syncResult.validation);
    });
  }, [syncIncomingProjectState]);

  useEffect(() => {
    const payload = buildProjectMetaPayload(formState);
    const serialized = JSON.stringify(payload);
    if (skipSaveRef.current) {
      skipSaveRef.current = false;
      lastPayloadRef.current = serialized;
      return;
    }
    if (lastPayloadRef.current === serialized) {
      return;
    }
    lastPayloadRef.current = serialized;
    lastSavedPayloadRef.current = serialized;
    onSaveMeta(payload);
  }, [formState, onSaveMeta]);

  const handleStateChange = useCallback(
    (patch: Partial<ProductInfoFormState>) => {
      setFormState((prev) => {
        const next: ProductInfoFormState = {
          ...prev,
          ...patch,
          productBrief: patch.productBrief ?? prev.productBrief,
          whatNotToSay: patch.whatNotToSay ?? prev.whatNotToSay,
          faq: patch.faq ?? prev.faq,
        };
        const validation = validateProductInfoMeta(next);
        setErrors(validation);
        return next;
      });
    },
    [],
  );

  useEffect(() => {
  const { payload, comparisonSignature, hasInvalidRow } = prepareVariantPayloads(variants);
  const serializedSignature = JSON.stringify(comparisonSignature);
  if (variantInitialSyncRef.current) {
    variantInitialSyncRef.current = false;
    lastVariantSentSignatureRef.current = serializedSignature;
    return;
  }
  if (hasInvalidRow) {
    return;
  }
  if (serializedSignature === lastVariantSentSignatureRef.current) {
    return;
  }
  lastVariantSentSignatureRef.current = serializedSignature;
  void saveVariants(payload, serializedSignature).catch(() => null);
}, [saveVariants, variants]);

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Product info intake
        </p>
        <p className="text-sm text-[#475569]">
          This step collects everything we need to build a high-quality Amazon product page: all
          SKUs, key product details, and brand guidelines. We’ll use this to generate titles,
          bullets, descriptions, and backend keywords in later steps.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <ProjectMetaForm
            value={formState}
            errors={errors}
            onChange={handleStateChange}
            marketplaceOptions={MARKETPLACE_OPTIONS}
          />
          <BrandGuidelinesForm
            brandTone={formState.brandTone}
            whatNotToSay={formState.whatNotToSay}
            onChange={handleStateChange}
          />
        </div>
        <div className="space-y-6">
          <ProductBriefForm
            productBrief={formState.productBrief}
            suppliedInfoNotes={formState.suppliedInfoNotes}
            onProductBriefChange={(brief) => handleStateChange({ productBrief: brief })}
            onSuppliedInfoChange={(notes) => handleStateChange({ suppliedInfoNotes: notes })}
          />
          <FaqRepeater
            faq={formState.faq}
            onChange={(items) => handleStateChange({ faq: items })}
          />
        </div>
      </div>

      <div className="space-y-6">
        <SkuTable
          projectId={projectId}
          variants={variants}
          isLoading={variantsLoading}
          error={variantsError}
          isSaving={variantsSaving}
          onDelete={deleteVariant}
          onChange={setVariants}
        />
        <AttributeSummaryPanel attributes={attributeSummary} isLoading={variantsLoading} />
      </div>
    </div>
  );
};
