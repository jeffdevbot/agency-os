import { useCallback, useEffect, useRef, useState } from "react";
import type { ComposerSkuVariant } from "@agency/lib/composer/types";

export interface SkuVariantInput {
  id?: string;
  sku: string;
  asin?: string | null;
  parentSku?: string | null;
  attributes?: Record<string, string | null>;
  notes?: string | null;
}

const serializeVariantSignature = (variants: Array<ComposerSkuVariant | SkuVariantInput>) => {
  const normalized = variants.map((variant) => ({
    sku: variant.sku,
    asin: variant.asin ?? null,
    parentSku: variant.parentSku ?? null,
    notes: variant.notes ?? null,
    attributes: variant.attributes ?? {},
  }));
  normalized.sort((a, b) => {
    if (a.sku !== b.sku) return a.sku.localeCompare(b.sku);
    if ((a.parentSku ?? "") !== (b.parentSku ?? "")) {
      return (a.parentSku ?? "").localeCompare(b.parentSku ?? "");
    }
    return 0;
  });
  return JSON.stringify(normalized);
};

interface UseSkuVariantsResult {
  variants: ComposerSkuVariant[];
  setVariants: React.Dispatch<React.SetStateAction<ComposerSkuVariant[]>>;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  saveVariants: (nextVariants: SkuVariantInput[], signature?: string) => Promise<void>;
  deleteVariant: (variantId: string) => Promise<void>;
  isSaving: boolean;
}

export const useSkuVariants = (projectId: string | undefined): UseSkuVariantsResult => {
  const [variants, setVariants] = useState<ComposerSkuVariant[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastExpectedSignatureRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/composer/projects/${projectId}/variants`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "Unable to load variants");
      }
      const serverVariants = (data.variants as ComposerSkuVariant[]) ?? [];
      lastExpectedSignatureRef.current = serializeVariantSignature(serverVariants);
      setVariants(serverVariants);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load variants");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveVariants = useCallback(
    async (nextVariants: SkuVariantInput[], signature?: string) => {
      if (!projectId) return;
      setIsSaving(true);
      setError(null);
      if (signature) {
        lastExpectedSignatureRef.current = signature;
      }
      try {
        const response = await fetch(`/api/composer/projects/${projectId}/variants`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ variants: nextVariants }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to save variants");
        }
        const serverVariants = (data.variants as ComposerSkuVariant[]) ?? [];
        const serverSignature = serializeVariantSignature(serverVariants);
        if (signature && signature !== serverSignature) {
          return;
        }
        if (signature && lastExpectedSignatureRef.current !== signature) {
          return;
        }
        lastExpectedSignatureRef.current = serverSignature;
        setVariants(serverVariants);
      } catch (saveError) {
        setError(saveError instanceof Error ? saveError.message : "Unable to save variants");
        throw saveError;
      } finally {
        setIsSaving(false);
      }
    },
    [projectId],
  );

  const deleteVariant = useCallback(
    async (variantId: string) => {
      if (!projectId) return;
      setError(null);
      try {
        const response = await fetch(
          `/api/composer/projects/${projectId}/variants/${variantId}`,
          {
            method: "DELETE",
          },
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to delete variant");
        }
        setVariants((prev) => prev.filter((variant) => variant.id !== variantId));
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Unable to delete variant");
        throw deleteError;
      }
    },
    [projectId],
  );

  return {
    variants,
    setVariants,
    isLoading,
    error,
    refresh,
    saveVariants,
    deleteVariant,
    isSaving,
  };
};
