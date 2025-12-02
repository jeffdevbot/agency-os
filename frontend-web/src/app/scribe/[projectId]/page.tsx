"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import clsx from "clsx";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import type { Session } from "@supabase/supabase-js";
import ProgressStepper from "./components/ProgressStepper";
import StageB from "./components/StageB";
import StageC from "./components/StageC";

type ScribeProjectStatus = "draft" | "stage_a_approved" | "stage_b_approved" | "stage_c_approved" | "approved" | "archived";

interface Project {
  id: string;
  name: string;
  status: ScribeProjectStatus | null;
  updatedAt?: string;
}

interface Sku {
  id: string;
  projectId: string;
  skuCode: string;
  asin: string | null;
  productName: string | null;
  brandTone: string | null;
  targetAudience: string | null;
  wordsToAvoid: string[];
  suppliedContent: string | null;
  sortOrder?: number | null;
}

interface Keyword {
  id: string;
  keyword: string;
  skuId: string;
}

interface Question {
  id: string;
  question: string;
  skuId: string;
}

interface VariantAttr {
  id: string;
  name: string;
  slug: string;
}

interface VariantValueMap {
  [attributeId: string]: {
    [skuId: string]: string;
  };
}

type InlineInputs = Record<string, string>;

function normalizeStatus(status: ScribeProjectStatus | string | null | undefined): ScribeProjectStatus {
  const value = typeof status === "string" ? status.toLowerCase() : "draft";
  if (value === "stage_a_approved") return "stage_a_approved";
  if (value === "stage_b_approved") return "stage_b_approved";
  if (value === "stage_c_approved") return "stage_c_approved";
  if (value === "approved") return "approved";
  if (value === "archived") return "archived";
  return "draft";
}

function deriveStageFromStatus(status: ScribeProjectStatus | string | null | undefined): "stage_a" | "stage_b" | "stage_c" {
  const normalized = normalizeStatus(status);
  if (normalized === "stage_a_approved") return "stage_b";
  if (normalized === "stage_b_approved" || normalized === "stage_c_approved" || normalized === "approved")
    return "stage_c";
  return "stage_a";
}

export default function ScribeProjectPage() {
  const params = useParams();
  const projectId =
    typeof params.projectId === "string"
      ? params.projectId
      : Array.isArray(params.projectId)
        ? params.projectId[0]
        : "";
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);

  const [sessionChecked, setSessionChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [attributes, setAttributes] = useState<VariantAttr[]>([]);
  const [variantValues, setVariantValues] = useState<VariantValueMap>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const [attributeFormOpen, setAttributeFormOpen] = useState(false);
  const [attributeForm, setAttributeForm] = useState({ name: "" });
  const [attributeError, setAttributeError] = useState<string | null>(null);
  const [attributeLoading, setAttributeLoading] = useState(false);

  const [skuFormLoading, setSkuFormLoading] = useState(false);
  const [autoCreatedFirstSku, setAutoCreatedFirstSku] = useState(false);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);

  const [approveLoading, setApproveLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [activeStage, setActiveStage] = useState<"stage_a" | "stage_b" | "stage_c">("stage_a");
  const [hasSetInitialStage, setHasSetInitialStage] = useState(false);
  useEffect(() => {
    setError(null);
  }, [activeStage]);

  // Inline add inputs per SKU
  const [wordInputs, setWordInputs] = useState<InlineInputs>({});
  const [keywordInputs, setKeywordInputs] = useState<InlineInputs>({});
  const [questionInputs, setQuestionInputs] = useState<InlineInputs>({});
  // Auth
  useEffect(() => {
    supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => {
      setIsAuthenticated(!!data.session);
      setSessionChecked(true);
    });
  }, [supabase]);

  // Load core data
  useEffect(() => {
    if (!isAuthenticated || !projectId) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`/api/scribe/projects/${projectId}`, { signal: controller.signal }),
      fetch(`/api/scribe/projects/${projectId}/skus`, { signal: controller.signal }),
      fetch(`/api/scribe/projects/${projectId}/keywords`, { signal: controller.signal }),
      fetch(`/api/scribe/projects/${projectId}/questions`, { signal: controller.signal }),
      fetch(`/api/scribe/projects/${projectId}/variant-attributes`, { signal: controller.signal }),
    ])
      .then(async ([projectRes, skusRes, keywordsRes, questionsRes, attrsRes]) => {
        if (!projectRes.ok) throw new Error((await projectRes.json()).error?.message ?? "Project load failed");
        if (!skusRes.ok) throw new Error((await skusRes.json()).error?.message ?? "SKUs load failed");
        if (!keywordsRes.ok) throw new Error((await keywordsRes.json()).error?.message ?? "Keywords load failed");
        if (!questionsRes.ok) throw new Error((await questionsRes.json()).error?.message ?? "Questions load failed");
        if (!attrsRes.ok) throw new Error((await attrsRes.json()).error?.message ?? "Attributes load failed");

        const projectData = (await projectRes.json()) as Project;
        const skusData = (await skusRes.json()) as Sku[];
        const keywordsData = (await keywordsRes.json()) as Keyword[];
        const questionsData = (await questionsRes.json()) as Question[];
        const attrsData = (await attrsRes.json()) as VariantAttr[];

        setProject(projectData);
        setSkus(skusData);
        setKeywords(keywordsData);
        setQuestions(questionsData);
        setAttributes(attrsData);
        setExpanded((prev) => {
          const next = { ...prev };
          skusData.forEach((s) => {
            if (next[s.id] === undefined) next[s.id] = true;
          });
          return next;
        });
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
        if (!controller.signal.aborted) setInitialDataLoaded(true);
      });
    return () => controller.abort();
  }, [isAuthenticated, projectId, refreshTick]);

  // Load variant values when attributes change
  useEffect(() => {
    if (!isAuthenticated || !projectId || attributes.length === 0) return;
    const controller = new AbortController();
    Promise.all(
      attributes.map((attr) =>
        fetch(`/api/scribe/projects/${projectId}/variant-attributes/${attr.id}/values`, {
          signal: controller.signal,
        }),
      ),
    )
      .then(async (responses) => {
        const valuesByAttr: VariantValueMap = {};
        for (let i = 0; i < responses.length; i++) {
          const res = responses[i];
          if (!res.ok) continue;
          const rows = (await res.json()) as { attributeId: string; skuId: string; value: string }[];
          const attrId = attributes[i].id;
          valuesByAttr[attrId] = rows.reduce<VariantValueMap[string]>((acc, row) => {
            acc[row.skuId] = row.value;
            return acc;
          }, {});
        }
        setVariantValues(valuesByAttr);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [attributes, isAuthenticated, projectId]);

  const bumpRefresh = () => setRefreshTick((t) => t + 1);

  // CRUD helpers
  const patchSku = async (skuId: string, body: Record<string, unknown>) => {
    const res = await fetch(`/api/scribe/projects/${projectId}/skus/${skuId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const payload = await res.json().catch(() => ({}));
      throw new Error(payload?.error?.message ?? "Failed to update SKU");
    }
  };

  const normalizedStatus = normalizeStatus(project?.status);
  const stageALocked = normalizedStatus !== "draft";

  // Helper: Check if we can unapprove each stage (must be at EXACT status, not beyond)
  const canUnapproveA = normalizedStatus === "stage_a_approved";
  const canUnapproveB = normalizedStatus === "stage_b_approved";
  const canUnapproveC = normalizedStatus === "stage_c_approved";

  // Helper: Check if we can navigate to each stage (stage must be unlocked)
  const canNavigateToB =
    normalizedStatus === "stage_a_approved" ||
    normalizedStatus === "stage_b_approved" ||
    normalizedStatus === "stage_c_approved" ||
    normalizedStatus === "approved";
  const canNavigateToC =
    normalizedStatus === "stage_b_approved" ||
    normalizedStatus === "stage_c_approved" ||
    normalizedStatus === "approved";

  const handleInlineSkuUpdate = async (skuId: string, field: keyof Sku, value: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      const body: Record<string, unknown> = {};
      // Map camelCase to API snake_case
      if (field === "skuCode") {
        const trimmed = value.trim();
        // Avoid sending null/empty to DB (NOT NULL constraint). Allow local empty UI.
        if (!trimmed) {
          setSkus((prev) => prev.map((s) => (s.id === skuId ? { ...s, [field]: "" } : s)));
          return;
        }
        body.sku_code = trimmed;
      }
      else if (field === "productName") body.product_name = value.trim() || null;
      else if (field === "brandTone") body.brand_tone = value.trim() || null;
      else if (field === "targetAudience") body.target_audience = value.trim() || null;
      else if (field === "suppliedContent") body.supplied_content = value.trim() || null;
      else body[field] = value.trim() || null;

      await patchSku(skuId, body);
      setSkus((prev) => prev.map((s) => (s.id === skuId ? { ...s, [field]: value } : s)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update SKU");
    }
  };

  const handleWordsChange = async (sku: Sku, nextWords: string[]) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      await patchSku(sku.id, { words_to_avoid: nextWords });
      setSkus((prev) => prev.map((s) => (s.id === sku.id ? { ...s, wordsToAvoid: nextWords } : s)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update words to avoid");
    }
  };

  const handleAddWord = (sku: Sku) => {
    const next = (wordInputs[sku.id] ?? "").trim();
    if (!next) return;
    setWordInputs((prev) => ({ ...prev, [sku.id]: "" }));
    const updated = [...(sku.wordsToAvoid ?? []), next];
    void handleWordsChange(sku, updated);
  };

  const handleDeleteWord = (sku: Sku, word: string) => {
    const updated = (sku.wordsToAvoid ?? []).filter((w) => w !== word);
    void handleWordsChange(sku, updated);
  };

  const handleAddKeyword = async (skuId: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    const value = (keywordInputs[skuId] ?? "").trim();
    if (!value) return;
    setKeywordInputs((prev) => ({ ...prev, [skuId]: "" }));
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/keywords`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: value, skuId }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.error?.message ?? "Failed to add keyword");
      }
      const created = (await res.json()) as Keyword;
      setKeywords((prev) => [...prev, created]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add keyword");
    }
  };

  const handleDeleteKeyword = async (id: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/keywords?id=${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete keyword");
      setKeywords((prev) => prev.filter((k) => k.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete keyword");
    }
  };

  const handleAddQuestion = async (skuId: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    const value = (questionInputs[skuId] ?? "").trim();
    if (!value) return;
    setQuestionInputs((prev) => ({ ...prev, [skuId]: "" }));
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: value, skuId }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.error?.message ?? "Failed to add question");
      }
      const created = (await res.json()) as Question;
      setQuestions((prev) => [...prev, created]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add question");
    }
  };

  const handleDeleteQuestion = async (id: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/questions?id=${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete question");
      setQuestions((prev) => prev.filter((q) => q.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete question");
    }
  };

  const handleAddSku = async () => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    setSkuFormLoading(true);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/skus`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to add SKU");
      }
      const created = (await res.json()) as Sku;
      setSkus((prev) => [...prev, { ...created, wordsToAvoid: created.wordsToAvoid ?? [] }]);
      setExpanded((prev) => ({ ...prev, [created.id]: true }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add SKU");
    } finally {
      setSkuFormLoading(false);
    }
  };

  const handleDeleteSku = async (id: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/skus/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete SKU");
      setSkus((prev) => prev.filter((s) => s.id !== id));
      setKeywords((prev) => prev.filter((k) => k.skuId !== id));
      setQuestions((prev) => prev.filter((q) => q.skuId !== id));
      setVariantValues((prev) => {
        const next: VariantValueMap = {};
        Object.entries(prev).forEach(([attrId, values]) => {
          const copy = { ...values };
          delete copy[id];
          next[attrId] = copy;
        });
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete SKU");
    }
  };

  const handleSaveVariantValue = async (attributeId: string, skuId: string, value: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes/${attributeId}/values`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skuId, value: value.trim() || null }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to save value");
      }

      const trimmed = value.trim();
      setVariantValues((prev) => {
        const nextAttrValues = { ...(prev[attributeId] ?? {}) };

        if (trimmed) {
          nextAttrValues[skuId] = trimmed;
        } else {
          // Delete key when value is cleared (POST deletes DB row)
          delete nextAttrValues[skuId];
        }

        return {
          ...prev,
          [attributeId]: nextAttrValues,
        };
      });
    } catch (err) {
      setAttributeError(err instanceof Error ? err.message : "Failed to save value");
    }
  };

  const handleAddAttribute = async () => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    const name = attributeForm.name.trim();
    if (!name) {
      setAttributeError("Attribute name is required");
      return;
    }
    setAttributeLoading(true);
    setAttributeError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to add attribute");
      }
      const created = (await res.json()) as VariantAttr;
      setAttributeForm({ name: "" });
      setAttributeFormOpen(false);
      setAttributes((prev) => [...prev, created]);
      setVariantValues((prev) => ({ ...prev, [created.id]: {} }));
    } catch (err) {
      setAttributeError(err instanceof Error ? err.message : "Failed to add attribute");
    } finally {
      setAttributeLoading(false);
    }
  };

  const handleDeleteAttribute = async (attributeId: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes?id=${attributeId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to delete attribute");
      }
      setAttributes((prev) => prev.filter((a) => a.id !== attributeId));
      setVariantValues((prev) => {
        const next = { ...prev };
        delete next[attributeId];
        return next;
      });
    } catch (err) {
      setAttributeError(err instanceof Error ? err.message : "Failed to delete attribute");
    }
  };

  const handleApproveStageA = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/approve-stage-a`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to approve Stage A");
      }
      const data = await res.json();
      setProject((prev) => (prev ? { ...prev, status: data.status ?? prev.status } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve Stage A");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleUnapproveStageA = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/unapprove-stage-a`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to unapprove Stage A");
      }
      const data = await res.json();
      setProject((prev) => (prev ? { ...prev, status: data.status ?? prev.status } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unapprove Stage A");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleApproveStageB = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/approve-topics`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to approve Stage B");
      }
      const data = await res.json();
      setProject((prev) => (prev ? { ...prev, status: data.status ?? prev.status } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve Stage B");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleUnapproveStageB = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/unapprove-topics`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to unapprove Stage B");
      }
      const data = await res.json();
      setProject((prev) => (prev ? { ...prev, status: data.status ?? prev.status } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unapprove Stage B");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleApproveStageC = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/approve-copy`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to approve Stage C");
      }
      const data = await res.json();
      setProject((prev) => (prev ? { ...prev, status: data.status ?? prev.status } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve Stage C");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleUnapproveStageC = async () => {
    setApproveLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/unapprove-copy`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to unapprove Stage C");
      }
      const data = await res.json();
      setProject((prev) => (prev ? { ...prev, status: data.status ?? prev.status } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unapprove Stage C");
    } finally {
      setApproveLoading(false);
    }
  };

  const handleExportCsv = async () => {
    setExportLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/export`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to export CSV");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `scribe-export-${projectId}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to export CSV");
    } finally {
      setExportLoading(false);
    }
  };

  // Auto-create first SKU when empty
  useEffect(() => {
    if (
      initialDataLoaded &&
      !loading &&
      skus.length === 0 &&
      !skuFormLoading &&
      !autoCreatedFirstSku
    ) {
      setAutoCreatedFirstSku(true);
      void handleAddSku();
    }
  }, [initialDataLoaded, loading, skus.length, skuFormLoading, autoCreatedFirstSku]);

  // Auto-set active stage based on project status (ONLY on initial page load, not on status changes)
  useEffect(() => {
    if (!project || !initialDataLoaded || hasSetInitialStage) return;

    setActiveStage(deriveStageFromStatus(project.status));
    setHasSetInitialStage(true);
  }, [project, initialDataLoaded, hasSetInitialStage]);

  const downloadCsv = () => {
    // CSV escape helper: quote all fields and escape internal quotes, strip newlines
    const escapeCSV = (value: string | null | undefined): string => {
      if (value === null || value === undefined) return '""';
      const str = String(value).replace(/[\r\n]+/g, ' '); // Strip newlines
      return `"${str.replace(/"/g, '""')}"`;
    };

    const headers = [
      "sku_code",
      "asin",
      "product_name",
      "brand_tone",
      "target_audience",
      "supplied_content",
      ...attributes.map((a) => a.slug),
      "words_to_avoid",
      "keywords",
      "questions",
    ];

    const headerRow = headers.map(escapeCSV).join(",");

    const rows = skus.map((sku) => {
      const wordsCell = (sku.wordsToAvoid ?? []).join("|");
      const skuKeywords = keywords.filter((k) => k.skuId === sku.id).map((k) => k.keyword).join("|");
      const skuQuestions = questions.filter((q) => q.skuId === sku.id).map((q) => q.question).join("|");
      const attrCells = attributes.map((a) => variantValues[a.id]?.[sku.id] ?? "");
      return [
        escapeCSV(sku.skuCode),
        escapeCSV(sku.asin ?? ""),
        escapeCSV(sku.productName ?? ""),
        escapeCSV(sku.brandTone ?? ""),
        escapeCSV(sku.targetAudience ?? ""),
        escapeCSV(sku.suppliedContent ?? ""),
        ...attrCells.map(escapeCSV),
        escapeCSV(wordsCell),
        escapeCSV(skuKeywords),
        escapeCSV(skuQuestions),
      ].join(",");
    });

    const BOM = '\uFEFF'; // UTF-8 BOM for Excel compatibility
    const csv = BOM + headerRow + "\n" + rows.join("\n");
    const blob = new Blob([csv], { type: "text/csv; charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "scribe_stage_a.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const uploadCsv = async (file: File) => {
    const text = await file.text();
    const stripBullets = (input: string) => input.replace(/[\u2022\u2023\u25E6\u2043\u2219]\s*/g, "").trim();

    const parseCsv = (input: string): string[][] => {
      const rows: string[][] = [];
      let row: string[] = [];
      let cell = "";
      let inQuotes = false;
      for (let i = 0; i < input.length; i++) {
        const ch = input[i];
        const next = input[i + 1];
        if (ch === '"' && inQuotes && next === '"') {
          cell += '"';
          i++;
          continue;
        }
        if (ch === '"') {
          inQuotes = !inQuotes;
          continue;
        }
        if (ch === "," && !inQuotes) {
          row.push(cell);
          cell = "";
          continue;
        }
        if ((ch === "\n" || ch === "\r") && !inQuotes) {
          if (cell !== "" || row.length > 0) {
            row.push(cell);
            rows.push(row);
            row = [];
            cell = "";
          }
          if (ch === "\r" && next === "\n") {
            i++;
          }
          continue;
        }
        cell += ch;
      }
      if (cell !== "" || row.length > 0) {
        row.push(cell);
        rows.push(row);
      }
      return rows;
    };

    const rows = parseCsv(text);
    if (!rows.length) return;
    const headers = rows[0].map((h) => h.trim().toLowerCase());
    const dataRows = rows.slice(1);

    for (const row of dataRows) {
      const record: Record<string, string> = {};
      headers.forEach((h, idx) => {
        record[h] = row[idx] ?? "";
      });

      const hasContent = Object.values(record).some((v) => v && v.trim() !== "");
      if (!hasContent) continue;

      const skuCode = record["sku_code"]?.trim() ?? "";
      if (!skuCode) continue;

      const existing = skus.find((s) => (s.skuCode ?? "").trim().toLowerCase() === skuCode.toLowerCase());
      let skuId = existing?.id;

      if (!skuId) {
        const skuRes = await fetch(`/api/scribe/projects/${projectId}/skus`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            skuCode,
            asin: record["asin"]?.trim() || null,
            productName: record["product_name"]?.trim() || null,
          }),
        });
        if (!skuRes.ok) continue;
        const createdSku = (await skuRes.json()) as Sku;
        skuId = createdSku.id;
        setSkus((prev) => [...prev, { ...createdSku, wordsToAvoid: createdSku.wordsToAvoid ?? [] }]);
      }

      const words = (record["words_to_avoid"] ?? "")
        .split("|")
        .map((w) => w.trim())
        .filter(Boolean);
      const brandTone = record["brand_tone"]?.trim() || null;
      const targetAudience = record["target_audience"]?.trim() || null;
      const suppliedContentRaw = record["supplied_content"] ?? "";
      const suppliedContent = suppliedContentRaw ? stripBullets(suppliedContentRaw) : null;

      // Patch scalar fields and words_to_avoid
      await fetch(`/api/scribe/projects/${projectId}/skus/${skuId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brand_tone: brandTone,
          target_audience: targetAudience,
          supplied_content: suppliedContent,
          words_to_avoid: words,
        }),
      });
      setSkus((prev) =>
        prev.map((s) => {
          if (s.id === skuId) {
            return { ...s, brandTone, targetAudience, suppliedContent, wordsToAvoid: words };
          }
          return s;
        }),
      );

      const keywordsCells = (record["keywords"] ?? "")
        .split("|")
        .map((w) => w.trim())
        .filter(Boolean);

      if (keywordsCells.length > 0) {
        const existingKeywords = keywords.filter((k) => k.skuId === skuId);
        for (const kw of existingKeywords) {
          await fetch(`/api/scribe/projects/${projectId}/keywords?id=${kw.id}`, { method: "DELETE" });
        }
        setKeywords((prev) => prev.filter((k) => k.skuId !== skuId));
      }

      for (const kw of keywordsCells) {
        const kwRes = await fetch(`/api/scribe/projects/${projectId}/keywords`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword: kw, skuId }),
        });
        if (kwRes.ok) {
          const created = (await kwRes.json()) as Keyword;
          setKeywords((prev) => [...prev, created]);
        }
      }

      const questionsCells = (record["questions"] ?? "")
        .split("|")
        .map((w) => w.trim())
        .filter(Boolean);

      if (questionsCells.length > 0) {
        const existingQuestions = questions.filter((q) => q.skuId === skuId);
        for (const q of existingQuestions) {
          await fetch(`/api/scribe/projects/${projectId}/questions?id=${q.id}`, { method: "DELETE" });
        }
        setQuestions((prev) => prev.filter((q) => q.skuId !== skuId));
      }

      for (const q of questionsCells) {
        const qRes = await fetch(`/api/scribe/projects/${projectId}/questions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, skuId }),
        });
        if (qRes.ok) {
          const created = (await qRes.json()) as Question;
          setQuestions((prev) => [...prev, created]);
        }
      }

      // Process variant attribute values
      for (const attr of attributes) {
        const attrValue = record[attr.slug.toLowerCase()]?.trim() || "";

        // POST to variant values API (empty string triggers delete)
        const valRes = await fetch(
          `/api/scribe/projects/${projectId}/variant-attributes/${attr.id}/values`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ skuId, value: attrValue }),
          }
        );

        if (valRes.ok) {
          // Update local state
          if (attrValue) {
            setVariantValues((prev) => ({
              ...prev,
              [attr.id]: {
                ...(prev[attr.id] ?? {}),
                [skuId]: attrValue,
              },
            }));
          } else {
            // Clear value from local state
            setVariantValues((prev) => {
              const nextAttrValues = { ...(prev[attr.id] ?? {}) };
              delete nextAttrValues[skuId];
              return {
                ...prev,
                [attr.id]: nextAttrValues,
              };
            });
          }
        }
      }
    }
  };

  const handleCopyFromSku = async (targetSkuId: string, sourceSkuId: string) => {
    if (stageALocked) {
      setError("Stage A is locked (later stages approved). Unapprove to edit.");
      return;
    }
    if (!sourceSkuId) return;
    try {
      const res = await fetch(`/api/scribe/projects/${projectId}/skus/${targetSkuId}/copy-from/${sourceSkuId}`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Copy failed");
      }
      bumpRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to copy from SKU");
    }
  };

  const getKeywordCount = (skuId: string) => keywords.filter((k) => k.skuId === skuId).length;
  const getQuestionCount = (skuId: string) => questions.filter((q) => q.skuId === skuId).length;

  if (!sessionChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">
        Checking authentication…
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">
        Please sign in to use Scribe.
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-6 py-8">
      {/* Progress Stepper */}
      {project && (
        <ProgressStepper
          projectStatus={normalizedStatus}
          lastUpdated={project.updatedAt}
          onStageClick={(stageId) => {
            if (stageId === "stage_a" || stageId === "stage_b" || stageId === "stage_c") {
              setActiveStage(stageId);
              setError(null);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }
          }}
        />
      )}

      {activeStage === "stage_a" && (
        <>
          <header className="flex flex-col gap-1">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Stage A</p>
            <h1 className="text-2xl font-semibold text-slate-900">{project?.name ?? "Project"}</h1>
            <p className="text-sm text-slate-600">
              Per-SKU grouped grid. Each SKU has its own data; reuse is via Copy from SKU.
            </p>
          </header>
        </>
      )}

      {activeStage === "stage_b" && (
        <header className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Stage B</p>
          <h1 className="text-2xl font-semibold text-slate-900">{project?.name ?? "Project"}</h1>
          <p className="text-sm text-slate-600">
            Review and select exactly 5 topics per SKU to guide Stage C copy generation.
          </p>
        </header>
      )}

      {error && error !== "No valid fields provided" ? (
        <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {activeStage === "stage_a" && project && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            className="rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleAddSku}
            disabled={skuFormLoading || stageALocked}
          >
            {skuFormLoading ? "Adding…" : "Add SKU"}
          </button>
          <label
            className={clsx(
              "cursor-pointer rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50",
              stageALocked && "cursor-not-allowed opacity-50",
            )}
            aria-disabled={stageALocked}
          >
            Import CSV
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              disabled={stageALocked}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) await uploadCsv(file);
              }}
            />
          </label>
          <button
            className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            onClick={downloadCsv}
            disabled={stageALocked}
          >
            Download Template
          </button>
          <button
            className="rounded-2xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            onClick={() => setAttributeFormOpen((v) => !v)}
            disabled={stageALocked}
          >
            {attributeFormOpen ? "Close Attribute" : "Add Attribute"}
          </button>
          <div className="ml-auto flex items-center gap-3">
            <button
              disabled={project?.status === "archived" || approveLoading || (!canUnapproveA && stageALocked)}
              className="rounded-2xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={canUnapproveA ? handleUnapproveStageA : handleApproveStageA}
            >
              {approveLoading
                ? canUnapproveA
                  ? "Unapproving…"
                  : "Approving…"
                : canUnapproveA
                  ? "Unapprove Stage A"
                  : "Approve Stage A"}
            </button>
          </div>
        </div>
        <p className="text-xs text-slate-500">
        </p>

        {attributeFormOpen && (
          <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
            <input
              className="rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
              placeholder="Attribute name (e.g., Color)"
              value={attributeForm.name}
              onChange={(e) => setAttributeForm({ name: e.target.value })}
              disabled={stageALocked}
            />
            <button
              className="rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleAddAttribute}
              disabled={attributeLoading || stageALocked}
            >
              {attributeLoading ? "Adding…" : "Add"}
            </button>
            {attributeError ? <span className="text-xs text-red-600">{attributeError}</span> : null}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-slate-600">Loading…</p>
        ) : (
          <div className={clsx("flex flex-col gap-4", stageALocked && "opacity-60")}>
            {skus.map((sku) => {
              const skuKeywords = keywords.filter((k) => k.skuId === sku.id);
              const skuQuestions = questions.filter((q) => q.skuId === sku.id);
              const attrValues = attributes.map((a) => ({
                attr: a,
                value: variantValues[a.id]?.[sku.id] ?? "",
              }));
              const isExpanded = expanded[sku.id] ?? true;
              return (
                <div key={sku.id} className="rounded-xl border-2 border-slate-400 bg-white shadow-lg">
                  <div className="flex flex-col gap-3 px-4 py-3">
                    {/* Row 1: identity + attrs */}
                    <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] items-start gap-3">
                      <div className="flex items-center gap-2 min-w-[180px]">
                        <button
                          className="text-slate-500 transition hover:text-slate-700"
                          onClick={() =>
                            setExpanded((prev) => ({
                              ...prev,
                              [sku.id]: !isExpanded,
                            }))
                          }
                          aria-label={isExpanded ? "Collapse" : "Expand"}
                        >
                          {isExpanded ? "▾" : "▸"}
                        </button>
                        <InlineEdit
                          label="SKU"
                          value={sku.skuCode}
                        onSave={(v) => handleInlineSkuUpdate(sku.id, "skuCode", v)}
                        className="font-semibold text-slate-900"
                        disabled={stageALocked}
                        allowEmpty={true}
                      />
                      </div>
                      <InlineEdit
                        label="ASIN"
                        value={sku.asin ?? ""}
                        onSave={(v) => handleInlineSkuUpdate(sku.id, "asin", v)}
                        className="min-w-[180px]"
                        disabled={stageALocked}
                      />
                        <InlineEdit
                          label="Product Name"
                          value={sku.productName ?? ""}
                          onSave={(v) => handleInlineSkuUpdate(sku.id, "productName", v)}
                          className="min-w-[220px]"
                          disabled={stageALocked}
                        />
                      {attrValues.map(({ attr, value }) => (
                        <InlineEdit
                          key={attr.id}
                          label={attr.name}
                          value={value}
                          onSave={(v) => handleSaveVariantValue(attr.id, sku.id, v)}
                          className="min-w-[180px]"
                          onDelete={() => handleDeleteAttribute(attr.id)}
                          disabled={stageALocked}
                        />
                      ))}
                      <div className="ml-auto flex items-center justify-end gap-2 min-w-[200px]">
                        <select
                          className="rounded border border-slate-300 bg-white px-2 py-2 text-xs text-slate-700"
                          value=""
                          onChange={(e) => handleCopyFromSku(sku.id, e.target.value)}
                          disabled={stageALocked}
                        >
                          <option value="">Copy from SKU</option>
                          {skus
                            .filter((s) => s.id !== sku.id)
                            .map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.skuCode}
                              </option>
                            ))}
                        </select>
                        <button
                          className="rounded border border-slate-200 px-2 py-2 text-xs text-slate-600 transition hover:bg-red-50 hover:text-red-600"
                          onClick={() => handleDeleteSku(sku.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </div>

                    {/* Scalar modules */}
                    <div className="grid gap-3 md:grid-cols-3">
                      <ScalarModule
                        label="Brand tone"
                        value={sku.brandTone ?? ""}
                        rows={2}
                        onSave={async (val) => {
                          await handleInlineSkuUpdate(sku.id, "brandTone", val);
                        }}
                      />
                      <ScalarModule
                        label="Target audience"
                        value={sku.targetAudience ?? ""}
                        rows={2}
                        onSave={async (val) => {
                          await handleInlineSkuUpdate(sku.id, "targetAudience", val);
                        }}
                      />
                      <ScalarModule
                        label="Supplied content"
                        value={sku.suppliedContent ?? ""}
                        rows={4}
                        onSave={async (val) => {
                          await handleInlineSkuUpdate(sku.id, "suppliedContent", val);
                        }}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 bg-slate-50 px-4 py-2">
                    <div className="flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                      {sku.wordsToAvoid?.length ?? 0} words
                    </div>
                    <div className="flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                      {getKeywordCount(sku.id)} keywords
                    </div>
                    <div className="flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                      {getQuestionCount(sku.id)} questions
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="grid gap-4 px-4 pb-4 pt-2 md:grid-cols-3">
                      <MultiValueSection
                        title="Words to Avoid"
                        items={sku.wordsToAvoid ?? []}
                        placeholder="Add word"
                        addValue={wordInputs[sku.id] ?? ""}
                        onChangeAddValue={(v) => setWordInputs((prev) => ({ ...prev, [sku.id]: v }))}
                        onAdd={() => handleAddWord(sku)}
                        onDelete={(word) => handleDeleteWord(sku, word)}
                        note=""
                      />
                      <MultiValueSection
                        title="Keywords"
                        items={skuKeywords.map((k) => k.keyword)}
                        placeholder="Add keyword"
                        addValue={keywordInputs[sku.id] ?? ""}
                        onChangeAddValue={(v) => setKeywordInputs((prev) => ({ ...prev, [sku.id]: v }))}
                        onAdd={() => handleAddKeyword(sku.id)}
                        onDelete={(kw) => {
                          const row = skuKeywords.find((k) => k.keyword === kw);
                          if (row) void handleDeleteKeyword(row.id);
                        }}
                        note="Max 10"
                      />
                      <MultiValueSection
                        title="Questions"
                        items={skuQuestions.map((q) => q.question)}
                        placeholder="Add question"
                        addValue={questionInputs[sku.id] ?? ""}
                        onChangeAddValue={(v) => setQuestionInputs((prev) => ({ ...prev, [sku.id]: v }))}
                        onAdd={() => handleAddQuestion(sku.id)}
                        onDelete={(text) => {
                          const row = skuQuestions.find((q) => q.question === text);
                          if (row) void handleDeleteQuestion(row.id);
                        }}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
          </section>

          {/* Navigation Bar */}
          <div className="flex justify-end">
            <button
              className="rounded-2xl bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => setActiveStage("stage_b")}
              disabled={!canNavigateToB}
            >
              Next: Stage B →
            </button>
          </div>
        </>
      )}

      {/* Stage B */}
      {activeStage === "stage_b" && project && (
        <>
          {/* Top Navigation Bar */}
          <div className="flex items-center justify-between">
            <button
              className="rounded-2xl border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              onClick={() => setActiveStage("stage_a")}
            >
              ← Back to Stage A
            </button>
            <button
              className="rounded-2xl bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => setActiveStage("stage_c")}
              disabled={!canNavigateToC}
            >
              Next: Stage C →
            </button>
          </div>

          <StageB
            projectId={projectId}
            skus={skus}
            projectStatus={normalizedStatus}
            onApprove={handleApproveStageB}
            onUnapprove={handleUnapproveStageB}
            approveLoading={approveLoading}
          />

          {/* Bottom Next Button (convenience after scrolling) */}
          <div className="flex justify-end">
            <button
              className="rounded-2xl bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50"
              onClick={() => setActiveStage("stage_c")}
              disabled={!canNavigateToC}
            >
              Next: Stage C →
            </button>
          </div>
        </>
      )}

      {/* Stage C */}
      {activeStage === "stage_c" && (
        <>
          <header className="flex flex-col gap-1">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Stage C</p>
            <h1 className="text-2xl font-semibold text-slate-900">{project?.name ?? "Project"}</h1>
            <p className="text-sm text-slate-600">
              Generate and edit Amazon listing content based on your approved topics.
            </p>
          </header>

          {/* Navigation Bar */}
          <div className="flex justify-start">
            <button
              className="rounded-2xl border border-slate-300 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              onClick={() => setActiveStage("stage_b")}
            >
              ← Back to Stage B
            </button>
          </div>

          {project && (
            <StageC
              projectId={projectId}
              projectStatus={normalizedStatus}
              skus={skus}
              onApprove={handleApproveStageC}
              onUnapprove={handleUnapproveStageC}
              onExport={handleExportCsv}
              exportLoading={exportLoading}
              approveLoading={approveLoading}
              isArchived={project.status === "archived"}
            />
          )}
        </>
      )}
    </div>
  );
}

function InlineEdit({
  label,
  value,
  onSave,
  className,
  onDelete,
  disabled = false,
  allowEmpty = true,
}: {
  label: string;
  value: string;
  onSave: (v: string) => void;
  className?: string;
  onDelete?: () => void;
  disabled?: boolean;
  allowEmpty?: boolean;
}) {
  const [local, setLocal] = useState(value ?? "");
  useEffect(() => {
    const next = value ?? "";
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocal((prev) => (prev === next ? prev : next));
  }, [value]);
  return (
    <label
      className={clsx(
        "flex w-full flex-col gap-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-slate-700",
        disabled && "opacity-60",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate">{label}</span>
        {onDelete ? (
          <button
            type="button"
            className="text-slate-400 transition hover:text-red-600 disabled:cursor-not-allowed"
            onClick={() => {
              if (disabled) return;
              onDelete();
            }}
            disabled={disabled}
            aria-label={`Delete ${label}`}
          >
            ×
          </button>
        ) : null}
      </div>
      <input
        className={clsx(
          "w-full min-w-[140px] rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none",
          className,
          disabled && "bg-slate-100 cursor-not-allowed",
        )}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (disabled) return;
          if (!allowEmpty && local.trim() === "") {
            // revert to previous value if empty not allowed
            setLocal(value ?? "");
            return;
          }
          onSave(local);
        }}
        disabled={disabled}
      />
    </label>
  );
}

function ScalarModule({
  label,
  value,
  rows = 2,
  onSave,
}: {
  label: string;
  value: string;
  rows?: number;
  onSave: (v: string) => void;
}) {
  const [local, setLocal] = useState(value ?? "");
  useEffect(() => {
    const next = value ?? "";
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocal((prev) => (prev === next ? prev : next));
  }, [value]);
  return (
    <div className="rounded-lg border border-slate-300 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-600">{label}</span>
      </div>
      <textarea
        className="min-h-[80px] w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none"
        rows={rows}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => onSave(local)}
      />
    </div>
  );
}

function MultiValueSection({
  title,
  items,
  addValue,
  placeholder,
  onChangeAddValue,
  onAdd,
  onDelete,
  note,
}: {
  title: string;
  items: string[];
  addValue: string;
  placeholder: string;
  onChangeAddValue: (v: string) => void;
  onAdd: () => void;
  onDelete: (value: string) => void;
  note?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-600">{title}</span>
        {note ? <span className="text-[11px] text-slate-500">{note}</span> : null}
      </div>
      <div className="flex flex-col gap-2">
        {items.length === 0 ? (
          <p className="text-xs text-slate-500">No entries yet.</p>
        ) : (
          items.map((item, idx) => (
            <div key={`${item}-${idx}`} className="flex items-center justify-between rounded border border-slate-200 px-3 py-2">
              <span className="text-sm text-slate-800">{item}</span>
              <button
                className="text-xs text-red-600 hover:underline"
                onClick={() => onDelete(item)}
                aria-label={`Delete ${title}`}
              >
                ×
              </button>
            </div>
          ))
        )}
        <div className="flex items-center gap-2">
          <input
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            placeholder={placeholder}
            value={addValue}
            onChange={(e) => onChangeAddValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onAdd();
              }
            }}
          />
          <button
            className="rounded-2xl bg-[#0a6fd6] px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-[#0959ab]"
            onClick={onAdd}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
