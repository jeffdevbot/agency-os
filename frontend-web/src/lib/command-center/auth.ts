import { NextResponse } from "next/server";
import type { User } from "@supabase/supabase-js";
import type { SupabaseRouteClient } from "@/lib/supabase/serverClient";

type ApiErrorCode = "unauthorized" | "forbidden" | "server_error";

export const jsonError = (code: ApiErrorCode, message: string, status: number) =>
  NextResponse.json({ error: { code, message } }, { status });

export const requireSession = async (supabase: SupabaseRouteClient): Promise<
  | { user: User; errorResponse: null }
  | { user: null; errorResponse: ReturnType<typeof NextResponse.json> }
> => {
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error) {
    const status = (error as { status?: number }).status ?? 500;
    if (status === 401 || status === 403) {
      return { user: null, errorResponse: jsonError("unauthorized", "Unauthorized", 401) };
    }
    return { user: null, errorResponse: jsonError("server_error", error.message, 500) };
  }

  if (!user) {
    return { user: null, errorResponse: jsonError("unauthorized", "Unauthorized", 401) };
  }

  return { user, errorResponse: null };
};

export const requireAdmin = async (supabase: SupabaseRouteClient, user: User) => {
  const { data, error } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", user.id)
    .single();

  if (error) {
    return { isAdmin: false, errorResponse: jsonError("server_error", error.message, 500) };
  }

  if (!data?.is_admin) {
    return { isAdmin: false, errorResponse: jsonError("forbidden", "Forbidden", 403) };
  }

  return { isAdmin: true, errorResponse: null };
};
