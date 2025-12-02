import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";

interface UsageLogParams {
  tool?: string;
  projectId: string;
  userId: string;
  jobId?: string;
  skuId?: string;
  stage?: "stage_a" | "stage_b" | "stage_c";
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  model?: string;
}

/**
 * Best-effort token usage logger. Does not throw on failure.
 */
export const logUsage = async (params: UsageLogParams): Promise<void> => {
  try {
    const supabase = createSupabaseServiceClient();
    await supabase.from("scribe_usage_logs").insert({
      tool: params.tool ?? "scribe",
      project_id: params.projectId,
      user_id: params.userId,
      job_id: params.jobId,
      sku_id: params.skuId,
      stage: params.stage,
      prompt_tokens: params.promptTokens,
      completion_tokens: params.completionTokens,
      total_tokens: params.totalTokens,
      model: params.model,
    });
  } catch (error) {
    console.error("Failed to log usage", error);
  }
};
