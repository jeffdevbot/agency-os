"use server";

import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";

export type InternalUsageLogRow = {
  id: string;
  createdAt: string;
  tool: string;
  model: string | null;
  stage: string | null;
  userId: string;
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
  user: {
    id: string;
    email: string | null;
    displayName: string | null;
    fullName: string | null;
    avatarUrl: string | null;
  } | null;
};

export type InternalUsageGroup = {
  day: string; // YYYY-MM-DD
  userId: string;
  tool: string;
  model: string | null;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  user: InternalUsageLogRow["user"];
};

export type DailyUsageByTool = {
  day: string; // YYYY-MM-DD
  totalsByTool: Record<string, number>;
};

export type TopSpender = {
  userId: string;
  name: string;
  avatarUrl: string | null;
  totalTokens: number;
};

export type InternalUsageResult = {
  rangeDays: number;
  totalRows: number | null;
  logsLimit: number;
  logs: InternalUsageLogRow[];
  grouped: InternalUsageGroup[];
  dailyByTool: DailyUsageByTool[];
  topSpenders: TopSpender[];
};

const requireAdminOrThrow = async (): Promise<void> => {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error) throw new Error(error.message);
  if (!user) throw new Error("Unauthorized");

  const { data, error: profileError } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", user.id)
    .single();

  if (profileError) throw new Error(profileError.message);
  if (!data?.is_admin) throw new Error("Forbidden");
};

const getUtcDayStartMs = (date: Date): number => {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
};

const getUtcStartOfTodayIso = (): string => {
  const ms = getUtcDayStartMs(new Date());
  return new Date(ms).toISOString();
};

const DEFAULT_LOGS_LIMIT = 250;

export const getInternalUsage = async (
  dateRange: number = 30,
  logsLimit: number = DEFAULT_LOGS_LIMIT,
): Promise<InternalUsageResult> => {
  await requireAdminOrThrow();

  const rangeDays = Number.isFinite(dateRange) && dateRange > 0 ? Math.min(Math.floor(dateRange), 90) : 30;
  const endExclusiveIso = getUtcStartOfTodayIso();
  const endExclusiveMs = Date.parse(endExclusiveIso);
  const startMs = endExclusiveMs - rangeDays * 24 * 60 * 60 * 1000;
  const startIso = new Date(startMs).toISOString();

  const service = createSupabaseServiceClient();

  const pageSize = rangeDays <= 30 ? 5000 : 10000;
  const maxRows = rangeDays <= 30 ? 5000 : 1_000_000;

  const safeLogsLimit = Number.isFinite(logsLimit) && logsLimit > 0 ? Math.min(Math.floor(logsLimit), 1000) : 250;
  const recentRows: any[] = [];

  const groupedMap = new Map<string, Omit<InternalUsageGroup, "user">>();
  const dailyToolMap = new Map<string, Record<string, number>>();
  const userTotals = new Map<string, { totalTokens: number }>();
  const userIds = new Set<string>();

  for (let offset = 0; offset < maxRows; offset += pageSize) {
    const { data, error } = await service
      .from("ai_token_usage")
      .select(
        "id, created_at, tool, model, stage, user_id, prompt_tokens, completion_tokens, total_tokens",
      )
      .gte("created_at", startIso)
      .lt("created_at", endExclusiveIso)
      .order("created_at", { ascending: false })
      .range(offset, offset + pageSize - 1);

    if (error) throw new Error(error.message);
    const batch = data ?? [];
    if (batch.length === 0) break;

    for (const row of batch) {
      const userId = row.user_id as string | null;
      if (!userId) continue;
      userIds.add(userId);

      const createdAt = row.created_at as string;
      const day = createdAt.slice(0, 10);
      const tool = (row.tool as string) || "unknown";
      const model = (row.model as string | null) ?? null;
      const prompt = (row.prompt_tokens as number | null) ?? 0;
      const completion = (row.completion_tokens as number | null) ?? 0;
      const total = ((row.total_tokens as number | null) ?? null) ?? prompt + completion;

      const groupKey = `${day}|${userId}|${tool}|${model ?? ""}`;
      const existing = groupedMap.get(groupKey);
      if (existing) {
        existing.promptTokens += prompt;
        existing.completionTokens += completion;
        existing.totalTokens += total;
      } else {
        groupedMap.set(groupKey, {
          day,
          userId,
          tool,
          model,
          promptTokens: prompt,
          completionTokens: completion,
          totalTokens: total,
        });
      }

      const byTool = dailyToolMap.get(day) ?? {};
      byTool[tool] = (byTool[tool] ?? 0) + total;
      dailyToolMap.set(day, byTool);

      const existingUser = userTotals.get(userId);
      if (existingUser) {
        existingUser.totalTokens += total;
      } else {
        userTotals.set(userId, { totalTokens: total });
      }
    }

    if (recentRows.length < safeLogsLimit) {
      recentRows.push(...batch.slice(0, Math.max(0, safeLogsLimit - recentRows.length)));
    }

    if (batch.length < pageSize) break;
  }

  const userIdList = Array.from(userIds.values());
  const profilesById = new Map<
    string,
    { id: string; email: string | null; display_name: string | null; full_name: string | null; avatar_url: string | null }
  >();

  if (userIdList.length > 0) {
    const { data: profiles, error: profilesError } = await service
      .from("profiles")
      .select("id, email, display_name, full_name, avatar_url")
      .in("id", userIdList);
    if (profilesError) throw new Error(profilesError.message);
    for (const profile of profiles ?? []) {
      profilesById.set(profile.id as string, {
        id: profile.id as string,
        email: (profile.email as string | null) ?? null,
        display_name: (profile.display_name as string | null) ?? null,
        full_name: (profile.full_name as string | null) ?? null,
        avatar_url: (profile.avatar_url as string | null) ?? null,
      });
    }
  }

  const logs: InternalUsageLogRow[] = (recentRows ?? []).map((row) => {
    const profile = profilesById.get(row.user_id as string) ?? null;
    return {
      id: row.id as string,
      createdAt: row.created_at as string,
      tool: row.tool as string,
      model: (row.model as string | null) ?? null,
      stage: (row.stage as string | null) ?? null,
      userId: row.user_id as string,
      promptTokens: (row.prompt_tokens as number | null) ?? null,
      completionTokens: (row.completion_tokens as number | null) ?? null,
      totalTokens: (row.total_tokens as number | null) ?? null,
      user: profile
        ? {
            id: profile.id,
            email: profile.email,
            displayName: profile.display_name,
            fullName: profile.full_name,
            avatarUrl: profile.avatar_url,
          }
        : null,
    };
  });

  const grouped: InternalUsageGroup[] = Array.from(groupedMap.values())
    .map((entry) => {
      const profile = profilesById.get(entry.userId) ?? null;
      return {
        ...entry,
        user: profile
          ? {
              id: profile.id,
              email: profile.email,
              displayName: profile.display_name,
              fullName: profile.full_name,
              avatarUrl: profile.avatar_url,
            }
          : null,
      };
    })
    .sort((a, b) => b.day.localeCompare(a.day));

  const dailyByTool: DailyUsageByTool[] = Array.from({ length: rangeDays }, (_, idx) => {
    const day = new Date(startMs + idx * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    return { day, totalsByTool: dailyToolMap.get(day) ?? {} };
  });

  const topSpenders: TopSpender[] = Array.from(userTotals.entries())
    .map(([userId, meta]) => {
      const profile = profilesById.get(userId) ?? null;
      const name =
        profile?.display_name?.trim() ||
        profile?.full_name?.trim() ||
        profile?.email?.trim() ||
        userId.slice(0, 8);
      return { userId, name, avatarUrl: profile?.avatar_url ?? null, totalTokens: meta.totalTokens };
    })
    .sort((a, b) => b.totalTokens - a.totalTokens)
    .slice(0, 12);

  const { count, error: countError } = await service
    .from("ai_token_usage")
    .select("id", { count: "estimated", head: true })
    .gte("created_at", startIso)
    .lt("created_at", endExclusiveIso);

  return {
    rangeDays,
    totalRows: countError ? null : typeof count === "number" ? count : null,
    logsLimit: safeLogsLimit,
    logs,
    grouped,
    dailyByTool,
    topSpenders,
  };
};
