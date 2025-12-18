import type { NextRequest } from "next/server";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";

export const runtime = "nodejs";

const parseRangeDays = (raw: string | null): number => {
  const n = raw ? Number(raw) : NaN;
  if (!Number.isFinite(n)) return 7;
  if (n === 7 || n === 30 || n === 90) return n;
  return 7;
};

const getUtcStartOfTodayIso = (): string => {
  const now = new Date();
  const ms = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return new Date(ms).toISOString();
};

const estimateCostUsd = (model: string | null, promptTokens: number, completionTokens: number): number | null => {
  const pricingPer1M: Record<string, { input: number; output: number }> = {
    "gpt-4o-mini": { input: 0.15, output: 0.6 },
    "gpt-4o": { input: 2.5, output: 10 },
  };

  const name = model ?? "";
  const match =
    Object.entries(pricingPer1M).find(([prefix]) => name.startsWith(prefix))?.[1] ?? null;
  if (!match) return null;

  return (promptTokens / 1_000_000) * match.input + (completionTokens / 1_000_000) * match.output;
};

const csvEscape = (value: string): string => {
  if (value.includes('"') || value.includes(",") || value.includes("\n")) {
    return `"${value.replace(/\"/g, '""')}"`;
  }
  return value;
};

export async function GET(request: NextRequest): Promise<Response> {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error) return new Response(error.message, { status: 401 });
  if (!user) return new Response("Unauthorized", { status: 401 });

  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", user.id)
    .single();

  if (profileError) return new Response(profileError.message, { status: 500 });
  if (!profile?.is_admin) return new Response("Forbidden", { status: 403 });

  const rangeDays = parseRangeDays(request.nextUrl.searchParams.get("range"));
  const endExclusiveIso = getUtcStartOfTodayIso();
  const endExclusiveMs = Date.parse(endExclusiveIso);
  const startIso = new Date(endExclusiveMs - rangeDays * 24 * 60 * 60 * 1000).toISOString();

  const service = createSupabaseServiceClient();
  const encoder = new TextEncoder();

  const headers = new Headers();
  headers.set("Content-Type", "text/csv; charset=utf-8");
  headers.set("Content-Disposition", `attachment; filename="token-usage-${rangeDays}d.csv"`);
  headers.set("Cache-Control", "no-store");

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const writeLine = (line: string) => controller.enqueue(encoder.encode(line));

      writeLine(
        "time,user_id,user_name,tool,stage,model,prompt_tokens,completion_tokens,total_tokens,est_cost_usd\n",
      );

      const profilesById = new Map<
        string,
        { email: string | null; display_name: string | null; full_name: string | null; avatar_url: string | null }
      >();

      const pageSize = rangeDays <= 30 ? 5000 : 10000;
      const maxRows = rangeDays <= 30 ? 5000 : 1_000_000;

      for (let offset = 0; offset < maxRows; offset += pageSize) {
        const { data, error: logsError } = await service
          .from("ai_token_usage")
          .select("created_at, tool, model, stage, user_id, prompt_tokens, completion_tokens, total_tokens")
          .gte("created_at", startIso)
          .lt("created_at", endExclusiveIso)
          .order("created_at", { ascending: false })
          .range(offset, offset + pageSize - 1);

        if (logsError) {
          controller.error(new Error(logsError.message));
          return;
        }

        const batch = data ?? [];
        if (batch.length === 0) break;

        const missingIds = Array.from(
          new Set(
            batch
              .map((row) => (row.user_id as string | null) ?? null)
              .filter((id): id is string => typeof id === "string" && id.length > 0 && !profilesById.has(id)),
          ),
        );

        if (missingIds.length > 0) {
          const { data: profiles, error: profilesError } = await service
            .from("profiles")
            .select("id, email, display_name, full_name, avatar_url")
            .in("id", missingIds);

          if (profilesError) {
            controller.error(new Error(profilesError.message));
            return;
          }

          for (const p of profiles ?? []) {
            profilesById.set(p.id as string, {
              email: (p.email as string | null) ?? null,
              display_name: (p.display_name as string | null) ?? null,
              full_name: (p.full_name as string | null) ?? null,
              avatar_url: (p.avatar_url as string | null) ?? null,
            });
          }
        }

        for (const row of batch) {
          const createdAt = (row.created_at as string) ?? "";
          const tool = (row.tool as string) ?? "";
          const stage = (row.stage as string | null) ?? "";
          const model = (row.model as string | null) ?? "";
          const userId = (row.user_id as string) ?? "";
          const promptTokens = ((row.prompt_tokens as number | null) ?? 0) || 0;
          const completionTokens = ((row.completion_tokens as number | null) ?? 0) || 0;
          const totalTokens = ((row.total_tokens as number | null) ?? null) ?? promptTokens + completionTokens;

          const profile = profilesById.get(userId) ?? null;
          const userName =
            profile?.display_name?.trim() ||
            profile?.full_name?.trim() ||
            profile?.email?.trim() ||
            userId.slice(0, 8);

          const est = estimateCostUsd(model || null, promptTokens, completionTokens);

          const line = [
            createdAt,
            userId,
            userName,
            tool,
            stage,
            model,
            String(promptTokens),
            String(completionTokens),
            String(totalTokens),
            est === null ? "" : String(est),
          ]
            .map((v) => csvEscape(v))
            .join(",");

          writeLine(`${line}\n`);
        }

        if (batch.length < pageSize) break;
      }

      controller.close();
    },
  });

  return new Response(stream, { headers });
}
