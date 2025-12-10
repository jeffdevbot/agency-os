import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";

interface UsageLogParams {
    tool: string;
    projectId?: string;
    userId: string;
    jobId?: string;
    skuId?: string;
    stage?: string;
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
    model?: string;
    meta?: Record<string, unknown>;
}

/**
 * Best-effort token usage logger. Does not throw on failure.
 * Writes to `ai_token_usage` table.
 */
export const logUsage = async (params: UsageLogParams): Promise<void> => {
    try {
        const supabase = createSupabaseServiceClient();

        // Construct payload, omitting undefined
        const payload: Record<string, unknown> = {
            tool: params.tool,
            project_id: params.projectId,
            user_id: params.userId,
            job_id: params.jobId,
            sku_id: params.skuId,
            prompt_tokens: params.promptTokens,
            completion_tokens: params.completionTokens,
            total_tokens: params.totalTokens,
            model: params.model,
        };

        // Write stage to its own column, everything else to meta
        if (params.stage) {
            payload.stage = params.stage;
        }

        if (params.meta) {
            payload.meta = params.meta;
        }

        await supabase.from("ai_token_usage").insert(payload);
    } catch (error) {
        console.error("Failed to log usage", error);
    }
};
