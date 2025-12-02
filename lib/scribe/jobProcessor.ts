import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import { generateTopicsForSku } from "./topicsGenerator";

interface JobPayload {
  projectId: string;
  skuIds: string[];
  jobType: "topics";
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
}

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
    .select("created_by")
    .eq("id", projectId)
    .single();

  if (projectError || !project) {
    throw new Error(`Project not found: ${projectId}`);
  }

  const userId = project.created_by;

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
        await processSkuTopics(supabase, projectId, skuId, jobId, userId);
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
    // Fatal error - mark job as failed
    await supabase
      .from("scribe_generation_jobs")
      .update({
        status: "failed",
        error_message: error instanceof Error ? error.message : String(error),
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
    .select("value, variant_attribute_id, scribe_variant_attributes(name)")
    .eq("sku_id", skuId);

  // Build variant attributes map
  const variantAttributes: Record<string, string> = {};
  if (variantValues) {
    for (const vv of variantValues) {
      const attrName = (vv.scribe_variant_attributes as { name: string } | null)?.name;
      if (attrName) {
        variantAttributes[attrName] = vv.value;
      }
    }
  }

  // Generate topics
  const result = await generateTopicsForSku({
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
  });

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

  // Log usage telemetry
  await supabase.from("scribe_usage_logs").insert({
    tool: "scribe",
    project_id: projectId,
    user_id: userId,
    job_id: jobId,
    sku_id: skuId,
    prompt_tokens: result.tokensIn,
    completion_tokens: result.tokensOut,
    total_tokens: result.tokensTotal,
    model: result.model,
    created_at: new Date().toISOString(),
  });
};
