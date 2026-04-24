import { NextResponse } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

export async function POST(request: Request) {
  if (!BACKEND_URL) {
    return NextResponse.json({ detail: "NEXT_PUBLIC_BACKEND_URL not configured" }, { status: 500 });
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", session.user.id)
    .single();

  if (!profile?.is_admin) {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }

  const body = await request.json().catch(() => ({}));

  const upstream = await fetch(
    `${BACKEND_URL}/admin/reports/api-access/amazon-spapi/debug-generic-report`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );

  const data = await upstream.json().catch(() => ({ detail: "Invalid upstream JSON" }));
  return NextResponse.json(data, { status: upstream.status });
}
