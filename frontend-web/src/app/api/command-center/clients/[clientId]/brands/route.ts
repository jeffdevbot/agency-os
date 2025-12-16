import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireAdmin, requireSession } from "@/lib/command-center/auth";
import { asOptionalString, asStringArray, isUuid } from "@/lib/command-center/validators";

interface CreateBrandPayload {
  name?: unknown;
  productKeywords?: unknown;
  amazonMarketplaces?: unknown;
  clickupSpaceId?: unknown;
  clickupListId?: unknown;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ clientId: string }> },
) {
  const { clientId } = await params;

  if (!isUuid(clientId)) {
    const message =
      process.env.NODE_ENV === "production"
        ? "clientId is invalid"
        : `clientId is invalid: ${clientId}`;
    return NextResponse.json(
      { error: { code: "validation_error", message } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const adminResult = await requireAdmin(supabase, sessionResult.user);
  if (adminResult.errorResponse) return adminResult.errorResponse;

  const payload = (await request.json()) as CreateBrandPayload;
  const name = asOptionalString(payload.name);
  if (!name) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "name is required" } },
      { status: 400 },
    );
  }

  const productKeywords = asStringArray(payload.productKeywords);
  const amazonMarketplaces = asStringArray(payload.amazonMarketplaces);
  const clickupSpaceId = asOptionalString(payload.clickupSpaceId);
  const clickupListId = asOptionalString(payload.clickupListId);

  const now = new Date().toISOString();
  const { data, error } = await supabase
    .from("brands")
    .insert({
      client_id: clientId,
      name,
      product_keywords: productKeywords,
      amazon_marketplaces: amazonMarketplaces,
      clickup_space_id: clickupSpaceId,
      clickup_list_id: clickupListId,
      created_at: now,
      updated_at: now,
    })
    .select(
      "id, client_id, name, product_keywords, amazon_marketplaces, clickup_space_id, clickup_list_id, created_at, updated_at",
    )
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: { code: "server_error", message: error?.message ?? "Unable to create brand" } },
      { status: 500 },
    );
  }

  return NextResponse.json(
    {
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
    },
    { status: 201 },
  );
}
