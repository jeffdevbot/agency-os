import { NextResponse } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { requireSession } from "@/lib/command-center/auth";

export async function GET() {
  const supabase = await createSupabaseRouteClient();
  const sessionResult = await requireSession(supabase);
  if (sessionResult.errorResponse) return sessionResult.errorResponse;

  const { data, error } = await supabase
    .from("brands")
    .select("id, client_id, name, product_keywords, clickup_space_id, clickup_list_id, amazon_marketplaces")
    .order("name", { ascending: true });

  if (error) {
    return NextResponse.json(
      { error: { code: "server_error", message: error.message } },
      { status: 500 },
    );
  }

  return NextResponse.json({
    brands: (data ?? []).map((brand) => ({
      brandId: brand.id as string,
      clientId: brand.client_id as string,
      name: brand.name as string,
      productKeywords: (brand.product_keywords as string[] | null) ?? [],
      clickupSpaceId: (brand.clickup_space_id as string | null) ?? null,
      clickupListId: (brand.clickup_list_id as string | null) ?? null,
      amazonMarketplaces: (brand.amazon_marketplaces as string[] | null) ?? [],
    })),
  });
}

