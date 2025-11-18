import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs";
import type { Session } from "@supabase/supabase-js";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";

const isUuid = (value: string | undefined): value is string => {
  return typeof value === "string" && /^[0-9a-fA-F-]{36}$/.test(value);
};

const resolveComposerOrgIdFromSession = (session: Session | null): string => {
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
  return DEFAULT_COMPOSER_ORG_ID;
};

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string; variantId?: string }> },
) {
  const { projectId, variantId } = await context.params;
  if (!isUuid(projectId) || !isUuid(variantId)) {
    return NextResponse.json({ error: "invalid_id" }, { status: 400 });
  }

  const cookieStore = cookies();
  const supabase = createRouteHandlerClient({
    cookies: () => cookieStore,
  });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const organizationId = resolveComposerOrgIdFromSession(session);

  const { error } = await supabase
    .from("composer_sku_variants")
    .delete()
    .eq("organization_id", organizationId)
    .eq("project_id", projectId)
    .eq("id", variantId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
