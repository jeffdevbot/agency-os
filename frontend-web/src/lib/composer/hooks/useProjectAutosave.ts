"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ComposerProject,
  ComposerProjectStatus,
  StrategyType,
} from "@agency/lib/composer/types";
import type { ProjectMetaPayload } from "@/lib/composer/productInfo/types";

export type AutosaveStatus = "idle" | "saving" | "saved" | "error";

export interface UpdateComposerProjectPayload extends Partial<ProjectMetaPayload> {
  strategyType?: StrategyType | null;
  status?: ComposerProjectStatus;
  activeStep?: string | null;
}

interface UseProjectAutosaveOptions {
  onSaved?: (project: ComposerProject) => void;
  debounceMs?: number;
}

export const useProjectAutosave = (
  projectId: string,
  { onSaved, debounceMs = 800 }: UseProjectAutosaveOptions = {},
) => {
  const [status, setStatus] = useState<AutosaveStatus>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const queuedRef = useRef<UpdateComposerProjectPayload | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const flush = useCallback(async () => {
    const payload = queuedRef.current;
    if (!payload) return;
    queuedRef.current = null;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus("saving");
    try {
      const response = await fetch(`/api/composer/projects/${projectId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "Autosave failed");
      }
      const data: ComposerProject = await response.json();
      setStatus("saved");
      setLastSavedAt(new Date().toISOString());
      onSaved?.(data);
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      setStatus("error");
      console.error("Composer autosave error", error);
    }
  }, [onSaved, projectId]);

  const scheduleFlush = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      void flush();
    }, debounceMs);
  }, [debounceMs, flush]);

  const savePartial = useCallback(
    (partial: UpdateComposerProjectPayload) => {
      queuedRef.current = {
        ...(queuedRef.current ?? {}),
        ...partial,
      };
      setStatus("saving");
      scheduleFlush();
    },
    [scheduleFlush],
  );

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      abortRef.current?.abort();
    };
  }, []);

  return {
    savePartial,
    autosaveStatus: status,
    lastSavedAt,
  };
};
