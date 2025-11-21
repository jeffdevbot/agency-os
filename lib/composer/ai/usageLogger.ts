import type { UsageAction } from "@agency/lib/composer/types";

export interface LogUsageParams {
  // Supabase client is passed from caller; typed loosely here to avoid cross-package type resolution issues in builds.
  // Using PromiseLike instead of Promise to match Supabase's query builder which is awaitable but not a direct Promise.
  supabase: {
    from: (table: string) => {
      insert: (values: Record<string, unknown>) => PromiseLike<{ error: { message: string } | null }>;
    };
  };
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
    const { error } = await supabase.from("composer_usage_events").insert({
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

    if (error) {
      console.error("Failed to log usage event:", error);
    }
  } catch (err) {
    console.error("Exception while logging usage event:", err);
  }
};
