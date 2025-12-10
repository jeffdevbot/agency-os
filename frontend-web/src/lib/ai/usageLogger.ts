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
            project_id: params.projectId ?? null,
            user_id: params.userId,
            job_id: params.jobId ?? null,
            sku_id: params.skuId ?? null,
            prompt_tokens: params.promptTokens ?? null,
            completion_tokens: params.completionTokens ?? null,
            total_tokens: params.totalTokens ?? null,
            model: params.model ?? null,
        };

        // Write stage to its own column, everything else to meta
        if (params.stage) {
            payload.stage = params.stage;
        }

        if (params.meta) {
            payload.meta = params.meta;
        }

        const { error } = await supabase.from("ai_token_usage").insert(payload);

        if (error) {
            console.error("[usageLogger] Failed to log usage:", {
                tool: params.tool,
                error: error.message,
                code: error.code,
            });
        }
    } catch (error) {
        console.error("[usageLogger] Exception:", error instanceof Error ? error.message : String(error));
    }
};
