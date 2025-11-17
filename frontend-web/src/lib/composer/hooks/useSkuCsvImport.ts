"use client";

import { useCallback, useState } from "react";
import type { SkuVariantInput } from "./useSkuVariants";

interface ImportResult {
  variants: SkuVariantInput[];
  detectedAttributes: string[];
}

interface ImportPayload {
  source: "csv" | "paste";
  raw: string;
}

interface UseSkuCsvImportResult {
  isParsing: boolean;
  parseError: string | null;
  parseFromRaw: (projectId: string, payload: ImportPayload) => Promise<ImportResult>;
}

export const useSkuCsvImport = (): UseSkuCsvImportResult => {
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  const parseFromRaw = useCallback(
    async (projectId: string, payload: ImportPayload): Promise<ImportResult> => {
      setIsParsing(true);
      setParseError(null);
      try {
        const response = await fetch(`/api/composer/projects/${projectId}/variants/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to parse file");
        }
        return {
          variants: (data.variants as SkuVariantInput[]) ?? [],
          detectedAttributes: data.detectedAttributes ?? [],
        };
      } catch (error) {
        console.error("Composer CSV import parse error", error);
        const message = error instanceof Error ? error.message : "Unable to parse file";
        setParseError(message);
        throw error;
      } finally {
        setIsParsing(false);
      }
    },
    [],
  );

  return {
    isParsing,
    parseError,
    parseFromRaw,
  };
};
