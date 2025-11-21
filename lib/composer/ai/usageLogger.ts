import type { UsageAction } from "@agency/lib/composer/types";

export interface LogUsageParams {
  // Supabase client typed as `any` to avoid cross-package type resolution issues with Next.js Turbopack.
  // Runtime validation ensures correct response structure. See docs/composer/slice_02_staged_plan.md for Option B (type-only import).
  supabase: any;
  organizationId: string;
  projectId?: string | null;
  jobId?: string | null;
  action: UsageAction;
  model: string;
  tokensIn: number;
  tokensOut: number;
  tokensTotal: number;
  durationMs: number;
  meta?: Record<string, unknown>;
}

export const logUsageEvent = async (params: LogUsageParams): Promise<void> => {
  const {
    supabase,
    organizationId,
    projectId,
    jobId,
    action,
    model,
    tokensIn,
    tokensOut,
    tokensTotal,
    durationMs,
    meta = {},
  } = params;

  try {
    const result = await supabase.from("composer_usage_events").insert({
      organization_id: organizationId,
      project_id: projectId,
      job_id: jobId,
      action,
      model,
      tokens_in: tokensIn,
      tokens_out: tokensOut,
      tokens_total: tokensTotal,
      duration_ms: durationMs,
      meta,
      cost_usd: null,
    });

    // Runtime validation of Supabase response structure
    if (result.error) {
      console.error("Failed to log usage event:", {
        message: result.error.message,
        code: result.error.code,
        details: result.error.details,
        hint: result.error.hint,
      });
      throw new Error(
        `Usage logging failed: ${result.error.message}${result.error.code ? ` (${result.error.code})` : ""}`,
      );
    }

    // Validate that insert succeeded (data should be present)
    if (!result.data) {
      console.warn(
        "Usage event insert returned no data - this may indicate an RLS policy issue",
      );
    }
  } catch (err) {
    // Re-throw errors we already handled, log and throw unexpected ones
    if (err instanceof Error && err.message.startsWith("Usage logging failed")) {
      throw err;
    }
    console.error("Exception while logging usage event:", err);
    throw new Error(
      `Unexpected error logging usage: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
};
