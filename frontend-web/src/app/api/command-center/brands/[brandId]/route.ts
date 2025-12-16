import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, asStringArray, isUuid } from "@/lib/command-center/validators";

interface PatchBrandPayload {
  name?: unknown;
  productKeywords?: unknown;
  amazonMarketplaces?: unknown;
  clickupSpaceId?: unknown;
  clickupListId?: unknown;
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ brandId: string }> },
) {
  const { brandId } = await params;

  if (!isUuid(brandId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "brandId is invalid" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const payload = (await request.json()) as PatchBrandPayload;
  const name = payload.name === undefined ? undefined : asOptionalString(payload.name);
  const clickupSpaceId = payload.clickupSpaceId === undefined ? undefined : asOptionalString(payload.clickupSpaceId);
  const clickupListId = payload.clickupListId === undefined ? undefined : asOptionalString(payload.clickupListId);

  const update: Record<string, unknown> = {
    updated_at: new Date().toISOString(),
  };

  if (name !== undefined) update.name = name;
  if (payload.productKeywords !== undefined) update.product_keywords = asStringArray(payload.productKeywords);
  if (payload.amazonMarketplaces !== undefined) update.amazon_marketplaces = asStringArray(payload.amazonMarketplaces);
  if (clickupSpaceId !== undefined) update.clickup_space_id = clickupSpaceId;
  if (clickupListId !== undefined) update.clickup_list_id = clickupListId;

  const { data, error } = await supabase
    .from("brands")
    .update(update)
    .eq("id", brandId)
    .select(
      "id, client_id, name, product_keywords, amazon_marketplaces, clickup_space_id, clickup_list_id, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to update brand" } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    brand: {
      id: data.id as string,
      clientId: data.client_id as string,
      name: data.name as string,
      productKeywords: (data.product_keywords as string[] | null) ?? [],
      amazonMarketplaces: (data.amazon_marketplaces as string[] | null) ?? [],
      clickupSpaceId: (data.clickup_space_id as string | null) ?? null,
      clickupListId: (data.clickup_list_id as string | null) ?? null,
      createdAt: data.created_at as string,
      updatedAt: data.updated_at as string,
    },
  });
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ brandId: string }> },
) {
  const { brandId } = await params;

  if (!isUuid(brandId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "brandId is invalid" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const { data: brand, error: brandError } = await supabase
    .from("brands")
    .select("id")
    .eq("id", brandId)
    .single();

  if (brandError || !brand) {
    return NextResponse.json(
      { error: { code: "server_error", message: brandError?.message ?? "Brand not found" } },
      { status: 500 },
    );
  }

  const service = createSupabaseServiceClient();

  const { error: assignmentsError } = await service
    .from("client_assignments")
    .delete()
    .eq("brand_id", brandId);
  if (assignmentsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: assignmentsError.message } },
      { status: 500 },
    );
  }

  const { error } = await service.from("brands").delete().eq("id", brandId);
  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true });
}
