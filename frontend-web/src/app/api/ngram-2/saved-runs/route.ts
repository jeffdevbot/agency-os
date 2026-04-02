import { NextResponse } from "next/server";

import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";

const DEFAULT_LIMIT = 5;
const MAX_LIMIT = 10;

const toText = (value: unknown): string | null => {
  const text = String(value ?? "").trim();
  return text || null;
};

const toNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const toRecommendationCounts = (
  value: unknown,
): { keep: number; negate: number; review: number } | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  return {
    keep: toNumber(record.keep) ?? 0,
    negate: toNumber(record.negate) ?? 0,
    review: toNumber(record.review) ?? 0,
  };
};

export async function GET(request: Request) {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const profileId = String(searchParams.get("profile_id") || "").trim();
  const adProduct = String(searchParams.get("ad_product") || "").trim().toUpperCase();
  const dateFrom = String(searchParams.get("date_from") || "").trim();
  const dateTo = String(searchParams.get("date_to") || "").trim();
  const respectLegacyExclusions = searchParams.get("respect_legacy_exclusions") !== "false";
  const limit = Math.max(
    1,
    Math.min(MAX_LIMIT, Number.parseInt(searchParams.get("limit") || String(DEFAULT_LIMIT), 10) || DEFAULT_LIMIT),
  );

  if (!profileId || !adProduct || !dateFrom || !dateTo) {
    return NextResponse.json(
      { detail: "profile_id, ad_product, date_from, and date_to are required" },
      { status: 400 },
    );
  }

  try {
    const service = createSupabaseServiceClient();
    const { data, error } = await service
      .from("ngram_ai_preview_runs")
      .select(
        [
          "id",
          "created_at",
          "ad_product",
          "date_from",
          "date_to",
          "spend_threshold",
          "respect_legacy_exclusions",
          "model",
          "prompt_version",
          "prompt_tokens",
          "completion_tokens",
          "total_tokens",
          "preview_payload",
        ].join(","),
      )
      .eq("requested_by_auth_user_id", user.id)
      .eq("profile_id", profileId)
      .eq("ad_product", adProduct)
      .eq("date_from", dateFrom)
      .eq("date_to", dateTo)
      .eq("respect_legacy_exclusions", respectLegacyExclusions)
      .order("created_at", { ascending: false })
      .limit(limit);

    if (error) {
      throw new Error(error.message);
    }

    const runs = (Array.isArray(data) ? data : []).map((row) => {
      const record = row as unknown as Record<string, unknown>;
      const payload =
        record.preview_payload && typeof record.preview_payload === "object" && !Array.isArray(record.preview_payload)
          ? (record.preview_payload as Record<string, unknown>)
          : {};
      const campaignCards = Array.isArray(payload.campaigns) ? payload.campaigns.length : null;

      return {
        id: toText(record.id),
        created_at: toText(record.created_at),
        ad_product: toText(record.ad_product),
        date_from: toText(record.date_from),
        date_to: toText(record.date_to),
        spend_threshold: toNumber(record.spend_threshold) ?? 0,
        respect_legacy_exclusions: Boolean(record.respect_legacy_exclusions),
        model: toText(record.model),
        prompt_version: toText(record.prompt_version),
        prompt_tokens: toNumber(record.prompt_tokens) ?? 0,
        completion_tokens: toNumber(record.completion_tokens) ?? 0,
        total_tokens: toNumber(record.total_tokens) ?? 0,
        run_mode: toText(payload.run_mode) ?? "preview",
        prefill_strategy: toText(payload.prefill_strategy),
        preview_campaigns: toNumber(payload.preview_campaigns) ?? campaignCards ?? 0,
        runnable_campaigns: toNumber(payload.runnable_campaigns) ?? 0,
        recommendation_counts: toRecommendationCounts(payload.recommendation_counts),
      };
    });

    return NextResponse.json({ runs });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to load saved runs" },
      { status: 500 },
    );
  }
}
