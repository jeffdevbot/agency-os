"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import { IngestScreen } from "./components/IngestScreen";
import { WorkspaceScreen } from "./components/WorkspaceScreen";
import type { AuditResponse } from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
  throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
}

export default function AdScopePage() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [auditData, setAuditData] = useState<AuditResponse | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAudit = useCallback(
    async (bulkFile: File, strFile: File, brandKeywords: string) => {
      setProcessing(true);
      setError(null);

      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const accessToken = sessionData.session?.access_token;

        if (!accessToken) {
          setError("Please sign in again.");
          setProcessing(false);
          return;
        }

        const formData = new FormData();
        formData.append("bulk_file", bulkFile);
        formData.append("str_file", strFile);
        formData.append("brand_keywords", brandKeywords);

        const response = await fetch(`${BACKEND_URL}/adscope/audit`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
          body: formData,
        });

        if (!response.ok) {
          const detail = await response.json().catch(() => undefined);
          throw new Error(detail?.detail || "Audit failed");
        }

        const data: AuditResponse = await response.json();
        setAuditData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Audit failed");
      } finally {
        setProcessing(false);
      }
    },
    [supabase]
  );

  const handleReset = useCallback(() => {
    setAuditData(null);
    setError(null);
  }, []);

  if (auditData) {
    return (
      <WorkspaceScreen
        auditData={auditData}
        onReset={handleReset}
      />
    );
  }

  return (
    <IngestScreen
      onSubmit={handleAudit}
      processing={processing}
      error={error}
    />
  );
}
