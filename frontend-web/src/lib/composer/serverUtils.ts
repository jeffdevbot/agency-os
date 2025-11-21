import type { Session } from "@supabase/supabase-js";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";

/**
 * Returns true when the provided value matches a canonical UUID string shape.
 */
export const isUuid = (value: unknown): value is string =>
  typeof value === "string" && /^[0-9a-fA-F-]{36}$/.test(value);

interface ResolveOrgIdOptions {
  /**
   * Legacy Composer endpoints optionally fall back to the default org. Pass `true`
   * only for those contexts to preserve behavior.
   */
  fallbackToDefault?: boolean;
}

/**
 * Pulls the Composer organization ID from Supabase session metadata.
 * Returns `null` when the org cannot be determined and no fallback is allowed.
 */
export const resolveComposerOrgIdFromSession = (
  session: Session | null,
  options: ResolveOrgIdOptions = {},
): string | null => {
  const { fallbackToDefault = false } = options;
  const userRecord = session?.user as Record<string, unknown> | undefined;
  const directField = userRecord?.org_id;

  if (typeof directField === "string" && directField.length > 0) {
    return directField;
  }

  const metadataOrgId =
    (session?.user?.app_metadata?.org_id as string | undefined) ??
    (session?.user?.user_metadata?.org_id as string | undefined) ??
    (session?.user?.app_metadata?.organization_id as string | undefined) ??
    (session?.user?.user_metadata?.organization_id as string | undefined);

  if (metadataOrgId && metadataOrgId.length > 0) {
    return metadataOrgId;
  }

  if (fallbackToDefault) {
    return DEFAULT_COMPOSER_ORG_ID;
  }

  return null;
};

/**
 * Helper function that validates organization ID from session and returns
 * appropriate error response if validation fails.
 *
 * This eliminates the need for manual null checks in every route.
 *
 * @example
 * ```typescript
 * export async function POST(request: NextRequest) {
 *   const supabase = await createSupabaseRouteClient();
 *   const result = await requireOrganizationId(supabase);
 *
 *   if (result.error) return result.error;
 *
 *   const organizationId = result.organizationId; // TypeScript knows this is string!
 *   // ... rest of route logic
 * }
 * ```
 */
export async function requireOrganizationId(
  supabase: Awaited<ReturnType<typeof import("@/lib/supabase/serverClient").createSupabaseRouteClient>>
): Promise<
  | { organizationId: string; error: null }
  | { organizationId: null; error: ReturnType<typeof import("next/server").NextResponse.json> }
> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    const { NextResponse } = await import("next/server");
    return {
      organizationId: null,
      error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }),
    };
  }

  const organizationId = resolveComposerOrgIdFromSession(session);

  if (!organizationId) {
    const { NextResponse } = await import("next/server");
    return {
      organizationId: null,
      error: NextResponse.json(
        { error: "Organization not found" },
        { status: 401 }
      ),
    };
  }

  return { organizationId, error: null };
}
