"use client";

import { useCallback, useEffect, useState } from "react";
import type { ComposerProject } from "@agency/lib/composer/types";

interface UseComposerProjectResult {
  project: ComposerProject | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
  refresh: () => Promise<void>;
  setProject: React.Dispatch<React.SetStateAction<ComposerProject | null>>;
}

export const useComposerProject = (projectId: string | undefined): UseComposerProjectResult => {
  const [project, setProject] = useState<ComposerProject | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchProject = useCallback(async () => {
    if (!projectId) {
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await fetch(`/api/composer/projects/${projectId}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "Unable to load project");
      }
      const data: ComposerProject = await response.json();
      setProject(data);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load project");
      setProject(null);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    void fetchProject();
  }, [fetchProject, projectId]);

  return {
    project,
    setProject,
    isLoading,
    isError: errorMessage !== null,
    errorMessage,
    refresh: fetchProject,
  };
};
