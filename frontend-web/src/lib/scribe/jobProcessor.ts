import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import { generateTopicsForSku } from "./topicsGenerator";
import { generateCopyForSku, type TitleGenerationMode } from "./copyGenerator";
import { logUsage } from "@/lib/ai/usageLogger";
import { logAppError } from "@/lib/ai/errorLogger";
import { assembleTitle, computeFixedTitleAndRemaining, parseTitleBlueprint, type SkuTitleData, type TitleBlueprint } from "./titleBlueprint";

interface JobPayload {
  projectId: string;
  skuIds: string[];
  jobType: "topics" | "copy";
  options: Record<string, unknown>;
}

interface SkuDataRow {
  id: string;
  sku_code: string;
  asin: string | null;
  product_name: string | null;
  brand_tone: string | null;
  target_audience: string | null;
  words_to_avoid: string[];
  supplied_content: string | null;
  attribute_preferences?: AttributePreferences | null;
}

type AttributePreferences = {
  mode?: "auto" | "overrides";
  rules?: Record<string, { sections: ("title" | "bullets" | "description" | "backend_keywords")[] }>;
} | null;

type FormatPreferences = {
  [key: string]: unknown;
  bulletCapsHeaders?: boolean;
  descriptionParagraphs?: boolean;
} | null;

const summarizeSkuErrors = (errors: Record<string, string>): Array<{ skuId: string; error: string }> => {
  return Object.entries(errors)
    .slice(0, 20)
    .map(([skuId, error]) => ({ skuId, error }));
};

export const processTopicsJob = async (jobId: string): Promise<void> => {
  const supabase = createSupabaseServiceClient();

  // Fetch job
  const { data: job, error: jobError } = await supabase
    .from("scribe_generation_jobs")
    .select("*")
    .eq("id", jobId)
    .single();

  if (jobError || !job) {
    throw new Error(`Job not found: ${jobId}`);
  }

  if (job.status !== "queued") {
    throw new Error(`Job ${jobId} is not in queued state (current: ${job.status})`);
  }

  const payload = job.payload as JobPayload;
  const { projectId, skuIds } = payload;

  // Fetch project to get user_id
  const { data: project, error: projectError } = await supabase
    .from("scribe_projects")
    .select("created_by, locale")
    .eq("id", projectId)
    .single();

  if (projectError || !project) {
    throw new Error(`Project not found: ${projectId}`);
  }

  const userId = project.created_by;
  const locale = (project as { locale?: string }).locale ?? "en-US";

  // Update job status to running
  await supabase
    .from("scribe_generation_jobs")
    .update({ status: "running" })
    .eq("id", jobId);

  const errors: Record<string, string> = {};
  let successCount = 0;

  try {
    // Process each SKU
    for (const skuId of skuIds) {
      try {
        await processSkuTopics(supabase, projectId, skuId, jobId, userId, locale);
        successCount++;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        errors[skuId] = errorMessage;
        console.error(`Failed to generate topics for SKU ${skuId}:`, errorMessage);
      }
    }

    // Update job status
    const finalStatus = Object.keys(errors).length === 0 ? "succeeded" : "failed";
    const finalPayload = {
      ...payload,
      errors: Object.keys(errors).length > 0 ? errors : undefined,
      successCount,
      totalCount: skuIds.length,
    };

    if (finalStatus === "failed") {
      await logAppError({
        tool: "scribe",
        message: `Topics job failed for ${Object.keys(errors).length} SKU(s)`,
        meta: {
          type: "scribe_topics_job_failed",
          jobId,
          projectId,
          successCount,
          totalCount: skuIds.length,
          skuErrors: summarizeSkuErrors(errors),
        },
      });
    }

    await supabase
      .from("scribe_generation_jobs")
      .update({
        status: finalStatus,
        payload: finalPayload,
        error_message:
          Object.keys(errors).length > 0
            ? `Failed for ${Object.keys(errors).length} SKU(s)`
            : null,
        completed_at: new Date().toISOString(),
      })
      .eq("id", jobId);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await logAppError({
      tool: "scribe",
      message,
      meta: { type: "scribe_topics_job_fatal", jobId, projectId },
    });
    // Fatal error - mark job as failed
    await supabase
      .from("scribe_generation_jobs")
      .update({
        status: "failed",
        error_message: message,
        completed_at: new Date().toISOString(),
      })
      .eq("id", jobId);

    throw error;
  }
};

const processSkuTopics = async (
  supabase: ReturnType<typeof createSupabaseServiceClient>,
  projectId: string,
  skuId: string,
  jobId: string,
  userId: string,
  locale: string,
): Promise<void> => {
  // Fetch SKU data
  const { data: sku, error: skuError } = await supabase
    .from("scribe_skus")
    .select("*")
    .eq("id", skuId)
    .eq("project_id", projectId)
    .single();

  if (skuError || !sku) {
    throw new Error(`SKU not found: ${skuId}`);
  }

  const skuData = sku as SkuDataRow;

  // Fetch keywords
  const { data: keywords } = await supabase
    .from("scribe_keywords")
    .select("keyword")
    .eq("sku_id", skuId)
    .order("priority", { ascending: false })
    .limit(10);

  // Fetch questions
  const { data: questions } = await supabase
    .from("scribe_customer_questions")
    .select("question")
    .eq("sku_id", skuId);

  // Fetch variant attributes and values
  const { data: variantValues } = await supabase
    .from("scribe_sku_variant_values")
    .select("value, attribute_id, scribe_variant_attributes(name)")
    .eq("sku_id", skuId);

  // Build variant attributes map
  const variantAttributes: Record<string, string> = {};
  if (variantValues) {
    for (const vv of variantValues) {
      const rel = vv.scribe_variant_attributes as unknown as
        | { name: string | null }
        | { name: string | null }[]
        | null;
      const attrName = Array.isArray(rel) ? rel[0]?.name : rel?.name;
      if (attrName) {
        variantAttributes[attrName] = vv.value;
      }
    }
  }

  // Generate topics
  const result = await generateTopicsForSku(
    {
      skuCode: skuData.sku_code,
      asin: skuData.asin,
      productName: skuData.product_name,
      brandTone: skuData.brand_tone,
      targetAudience: skuData.target_audience,
      wordsToAvoid: skuData.words_to_avoid ?? [],
      suppliedContent: skuData.supplied_content,
      keywords: (keywords ?? []).map((k) => k.keyword),
      questions: (questions ?? []).map((q) => q.question),
      variantAttributes,
    },
    locale,
  );

  // Delete existing topics for this SKU (regenerate behavior)
  await supabase.from("scribe_topics").delete().eq("sku_id", skuId);

  // Insert new topics
  const topicsToInsert = result.topics.map((topic) => ({
    project_id: projectId,
    sku_id: skuId,
    topic_index: topic.topicIndex,
    title: topic.title,
    description: topic.description,
    generated_by: "llm",
    approved: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }));

  const { error: insertError } = await supabase.from("scribe_topics").insert(topicsToInsert);

  if (insertError) {
    throw new Error(`Failed to insert topics: ${insertError.message}`);
  }

  // Best-effort usage telemetry
  await logUsage({
    projectId,
    userId,
    jobId,
    skuId,
    stage: "stage_b",
    tool: "scribe",
    promptTokens: result.tokensIn,
    completionTokens: result.tokensOut,
    totalTokens: result.tokensTotal,
    model: result.model,
  });
};

export const processCopyJob = async (jobId: string): Promise<void> => {
  const supabase = createSupabaseServiceClient();

  // Fetch job
  const { data: job, error: jobError } = await supabase
    .from("scribe_generation_jobs")
    .select("*")
    .eq("id", jobId)
    .single();

  if (jobError || !job) {
    throw new Error(`Job not found: ${jobId}`);
  }

  if (job.status !== "queued") {
    throw new Error(`Job ${jobId} is not in queued state (current: ${job.status})`);
  }

  const payload = job.payload as JobPayload;
  const { projectId, skuIds } = payload;

  // Fetch project to get user_id, locale, format_preferences and validate status
  const { data: project, error: projectError } = await supabase
    .from("scribe_projects")
    .select("created_by, status, locale, format_preferences")
    .eq("id", projectId)
    .single();

  if (projectError || !project) {
    throw new Error(`Project not found: ${projectId}`);
  }

  // Gate: reject archived projects only
  if (project.status === "archived") {
    throw new Error("Archived projects are read-only");
  }

  const userId = project.created_by;
  const locale = (project as { locale?: string }).locale ?? "en-US";
  const formatPreferences = (project as { format_preferences?: FormatPreferences | null }).format_preferences ?? undefined;
  const titleBlueprintRaw = (formatPreferences as Record<string, unknown> | null | undefined)?.title;
  const parsedTitleBlueprint = titleBlueprintRaw !== undefined ? parseTitleBlueprint(titleBlueprintRaw) : { blueprint: null, errors: [] };
  const titleBlueprint = parsedTitleBlueprint.blueprint;

  if (!titleBlueprint && parsedTitleBlueprint.errors.length > 0) {
    console.warn(`[Scribe] Invalid title blueprint for project ${projectId}:`, parsedTitleBlueprint.errors);
  }

  // Update job status to running
  await supabase
    .from("scribe_generation_jobs")
    .update({ status: "running" })
    .eq("id", jobId);

  const errors: Record<string, string> = {};
  let successCount = 0;

  try {
    // Process each SKU
    for (const skuId of skuIds) {
      try {
        await processSkuCopy(supabase, projectId, skuId, jobId, userId, locale, formatPreferences, titleBlueprint);
        successCount++;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        errors[skuId] = errorMessage;
        console.error(`Failed to generate copy for SKU ${skuId}:`, errorMessage);
      }
    }

    // Update job status
    const finalStatus = Object.keys(errors).length === 0 ? "succeeded" : "failed";
    const finalPayload = {
      ...payload,
      errors: Object.keys(errors).length > 0 ? errors : undefined,
      successCount,
      totalCount: skuIds.length,
    };

    if (finalStatus === "failed") {
      await logAppError({
        tool: "scribe",
        message: `Copy job failed for ${Object.keys(errors).length} SKU(s)`,
        meta: {
          type: "scribe_copy_job_failed",
          jobId,
          projectId,
          successCount,
          totalCount: skuIds.length,
          skuErrors: summarizeSkuErrors(errors),
        },
      });
    }

    await supabase
      .from("scribe_generation_jobs")
      .update({
        status: finalStatus,
        payload: finalPayload,
        error_message:
          Object.keys(errors).length > 0
            ? `Failed for ${Object.keys(errors).length} SKU(s)`
            : null,
        completed_at: new Date().toISOString(),
      })
      .eq("id", jobId);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await logAppError({
      tool: "scribe",
      message,
      meta: { type: "scribe_copy_job_fatal", jobId, projectId },
    });
    // Fatal error - mark job as failed
    await supabase
      .from("scribe_generation_jobs")
      .update({
        status: "failed",
        error_message: message,
        completed_at: new Date().toISOString(),
      })
      .eq("id", jobId);

    throw error;
  }
};

const processSkuCopy = async (
  supabase: ReturnType<typeof createSupabaseServiceClient>,
  projectId: string,
  skuId: string,
  jobId: string,
  userId: string,
  locale: string,
  formatPreferences?: FormatPreferences,
  titleBlueprint?: TitleBlueprint | null,
): Promise<void> => {
  // Fetch SKU data
  const { data: sku, error: skuError } = await supabase
    .from("scribe_skus")
    .select("*")
    .eq("id", skuId)
    .eq("project_id", projectId)
    .single();

  if (skuError || !sku) {
    throw new Error(`SKU not found: ${skuId}`);
  }

  const skuData = sku as SkuDataRow;

  // Fetch keywords
  const { data: keywords } = await supabase
    .from("scribe_keywords")
    .select("keyword")
    .eq("sku_id", skuId)
    .order("priority", { ascending: false })
    .limit(10);

  // Fetch questions
  const { data: questions } = await supabase
    .from("scribe_customer_questions")
    .select("question")
    .eq("sku_id", skuId);

  // Fetch variant attributes and values
  const { data: variantValues } = await supabase
    .from("scribe_sku_variant_values")
    .select("value, attribute_id, scribe_variant_attributes(name)")
    .eq("sku_id", skuId);

  // Build maps:
  // - variantAttributesByName: used by copy prompt + attribute rules (name-based)
  // - variantValuesByAttributeId: used by title blueprint (ID-based)
  const variantAttributesByName: Record<string, string> = {};
  const variantValuesByAttributeId: Record<string, string> = {};
  if (variantValues) {
    for (const vv of variantValues) {
      const rel = vv.scribe_variant_attributes as unknown as
        | { name: string | null }
        | { name: string | null }[]
        | null;
      const attrName = Array.isArray(rel) ? rel[0]?.name : rel?.name;
      const attrId = (vv as unknown as { attribute_id?: string }).attribute_id;
      if (attrName) {
        variantAttributesByName[attrName] = vv.value;
      }
      if (attrId) {
        variantValuesByAttributeId[attrId] = vv.value;
      }
    }
  }

  // Gate: re-validate exactly 5 selected topics exist
  const { count: topicCount, error: topicCountError } = await supabase
    .from("scribe_topics")
    .select("*", { count: "exact", head: true })
    .eq("sku_id", skuId)
    .eq("selected", true);

  if (topicCountError) {
    throw new Error(`Failed to validate topics: ${topicCountError.message}`);
  }

  if ((topicCount ?? 0) !== 5) {
    throw new Error(`SKU must have exactly 5 selected topics (found ${topicCount ?? 0})`);
  }

  // Fetch selected topics (exactly 5 required)
  const { data: selectedTopics, error: topicsError } = await supabase
    .from("scribe_topics")
    .select("title, description")
    .eq("sku_id", skuId)
    .eq("selected", true)
    .order("topic_index", { ascending: true })
    .limit(5);

  if (topicsError || !selectedTopics || selectedTopics.length !== 5) {
    throw new Error(`SKU must have exactly 5 selected topics (found ${selectedTopics?.length || 0})`);
  }

  // Parse attribute preferences from SKU (defaults to undefined for auto mode)
  const attributePreferences = skuData.attribute_preferences ?? undefined;

  // Generate copy
  const titleMode: TitleGenerationMode =
    titleBlueprint && titleBlueprint.blocks.some((b) => b.type === "llm_phrase")
      ? "feature_phrase"
      : titleBlueprint
        ? "none"
        : "full";

  let fixedTitleForBlueprint = "";
  let featurePhraseMaxChars = 0;
  if (titleBlueprint) {
    const skuTitleData: SkuTitleData = {
      productName: skuData.product_name,
      variantValuesByAttributeId,
    };
    const fixed = computeFixedTitleAndRemaining(skuTitleData, titleBlueprint);
    fixedTitleForBlueprint = fixed.fixedTitle;
    featurePhraseMaxChars = fixed.remainingForPhrase;

    if (fixedTitleForBlueprint.length > 200) {
      throw new Error(`Fixed title exceeds 200 characters (${fixedTitleForBlueprint.length} chars)`);
    }

    if (titleMode === "feature_phrase" && featurePhraseMaxChars <= 0) {
      throw new Error("Title blueprint leaves no room for Feature Phrase (AI); adjust blocks or separator");
    }
  }

  const result = await generateCopyForSku(
    {
      skuCode: skuData.sku_code,
      asin: skuData.asin,
      productName: skuData.product_name,
      brandTone: skuData.brand_tone,
      targetAudience: skuData.target_audience,
      wordsToAvoid: skuData.words_to_avoid ?? [],
      suppliedContent: skuData.supplied_content,
      keywords: (keywords ?? []).map((k) => k.keyword),
      questions: (questions ?? []).map((q) => q.question),
      variantAttributes: variantAttributesByName,
      approvedTopics: selectedTopics.map((t) => ({
        title: t.title,
        description: t.description || "",
      })),
      attributePreferences,
      formatPreferences: formatPreferences ?? undefined,
    },
    locale,
    titleBlueprint
      ? {
          titleMode,
          featurePhraseMaxChars,
          fixedTitleBase: fixedTitleForBlueprint,
          titleSeparator: titleBlueprint.separator,
        }
      : undefined,
  );

  const finalTitle =
    titleBlueprint && titleMode === "feature_phrase"
      ? assembleTitle(fixedTitleForBlueprint, titleBlueprint.separator, result.featurePhrase ?? "")
      : titleBlueprint
        ? fixedTitleForBlueprint
        : result.title ?? "";

  if (!finalTitle) {
    throw new Error("No title produced for SKU");
  }

  if (finalTitle.length > 200) {
    throw new Error(`Final title exceeds 200 characters (${finalTitle.length} chars)`);
  }

  // Fetch existing content to determine if this is an update
  const { data: existingContent } = await supabase
    .from("scribe_generated_content")
    .select("id, version")
    .eq("sku_id", skuId)
    .single();

  // Upsert generated content
  const contentData = {
    project_id: projectId,
    sku_id: skuId,
    title: finalTitle,
    bullets: result.bullets,
    description: result.description,
    backend_keywords: result.backendKeywords,
    model_used: result.model,
    prompt_version: result.promptVersion,
    version: existingContent ? (existingContent.version || 1) + 1 : 1,
    updated_at: new Date().toISOString(),
  };

  const { error: upsertError } = await supabase
    .from("scribe_generated_content")
    .upsert(contentData, { onConflict: "sku_id" });

  if (upsertError) {
    throw new Error(`Failed to save generated content: ${upsertError.message}`);
  }

  // Best-effort usage telemetry
  await logUsage({
    projectId,
    userId,
    jobId,
    skuId,
    stage: "stage_c",
    tool: "scribe",
    promptTokens: result.tokensIn,
    completionTokens: result.tokensOut,
    totalTokens: result.tokensTotal,
    model: result.model,
  });
};
