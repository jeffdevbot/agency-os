import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";

type ErrorSeverity = "error" | "warn" | "info";

export interface AppErrorEventInput {
  tool?: string;
  severity?: ErrorSeverity;
  message: string;
  route?: string;
  method?: string;
  statusCode?: number;
  requestId?: string;
  userId?: string;
  userEmail?: string;
  meta?: Record<string, unknown>;
}

const MAX_MESSAGE_LEN = 2000;
const MAX_STRING_META_LEN = 2000;
const MAX_META_KEYS = 50;
const REDACT_KEYS = /key|token|secret|authorization|password/i;

const truncate = (value: string, maxLen: number): string => {
  if (value.length <= maxLen) return value;
  return value.slice(0, Math.max(0, maxLen - 1)) + "…";
};

const sanitizeMetaValue = (value: unknown): unknown => {
  if (value === null || value === undefined) return value;
  if (typeof value === "string") return truncate(value, MAX_STRING_META_LEN);
  if (typeof value === "number" || typeof value === "boolean") return value;
  if (Array.isArray(value)) return value.slice(0, 50).map(sanitizeMetaValue);
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).slice(0, MAX_META_KEYS);
    const out: Record<string, unknown> = {};
    for (const [k, v] of entries) {
      if (REDACT_KEYS.test(k)) {
        out[k] = "[REDACTED]";
      } else {
        out[k] = sanitizeMetaValue(v);
      }
    }
    return out;
  }
  return String(value);
};

const sanitizeMeta = (meta: Record<string, unknown> | undefined): Record<string, unknown> => {
  if (!meta) return {};
  const sanitized = sanitizeMetaValue(meta);
  return typeof sanitized === "object" && sanitized !== null && !Array.isArray(sanitized)
    ? (sanitized as Record<string, unknown>)
    : { value: sanitized };
};

/**
 * Best-effort centralized error logger. Does not throw on failure.
 * Writes to `app_error_events` via service role.
 */
export const logAppError = async (input: AppErrorEventInput): Promise<void> => {
  try {
    const supabase = createSupabaseServiceClient();

    const payload = {
      tool: input.tool ?? null,
      severity: input.severity ?? "error",
      message: truncate(input.message || "Unknown error", MAX_MESSAGE_LEN),
      route: input.route ?? null,
      method: input.method ?? null,
      status_code: input.statusCode ?? null,
      request_id: input.requestId ?? null,
      user_id: input.userId ?? null,
      user_email: input.userEmail ?? null,
      meta: sanitizeMeta(input.meta),
    };

    const { error } = await supabase.from("app_error_events").insert(payload);
    if (error) {
      console.error("[errorLogger] Failed to log error:", error.message);
    }
  } catch (error) {
    console.error("[errorLogger] Exception:", error instanceof Error ? error.message : String(error));
  }
};

