import { NextResponse, type NextRequest } from "next/server";
import { DEFAULT_COMPOSER_ORG_ID } from "@/lib/composer/constants";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { isUuid, resolveComposerOrgIdFromSession } from "@/lib/composer/serverUtils";

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string; variantId?: string }> },
) {
  const { projectId, variantId } = await context.params;
  if (!isUuid(projectId) || !isUuid(variantId)) {
    return NextResponse.json({ error: "invalid_id" }, { status: 400 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const organizationId =
    resolveComposerOrgIdFromSession(session, { fallbackToDefault: true }) ??
    DEFAULT_COMPOSER_ORG_ID;

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
