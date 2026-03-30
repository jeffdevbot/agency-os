import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";

type PersistNgramPreviewRunParams = {
  profileId: string;
  requestedByAuthUserId: string;
  adProduct: string;
  dateFrom: string;
  dateTo: string;
  spendThreshold: number;
  respectLegacyExclusions: boolean;
  model: string | null;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  previewPayload: Record<string, unknown>;
};

export const persistNgramPreviewRun = async (
  params: PersistNgramPreviewRunParams,
): Promise<void> => {
  try {
    const supabase = createSupabaseServiceClient();
    const { error } = await supabase.from("ngram_ai_preview_runs").insert({
      profile_id: params.profileId,
      requested_by_auth_user_id: params.requestedByAuthUserId,
      ad_product: params.adProduct,
      date_from: params.dateFrom,
      date_to: params.dateTo,
      spend_threshold: params.spendThreshold,
      respect_legacy_exclusions: params.respectLegacyExclusions,
      model: params.model,
      prompt_tokens: params.promptTokens,
      completion_tokens: params.completionTokens,
      total_tokens: params.totalTokens,
      preview_payload: params.previewPayload,
    });

    if (error) {
      console.error("[ngramPreviewLogger] Failed to persist preview run:", {
        profileId: params.profileId,
        error: error.message,
        code: error.code,
      });
    }
  } catch (error) {
    console.error(
      "[ngramPreviewLogger] Exception:",
      error instanceof Error ? error.message : String(error),
    );
  }
};
