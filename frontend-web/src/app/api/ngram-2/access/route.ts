import { NextResponse } from "next/server";

import {
  listAccessibleNgram2Summaries,
  getNgram2AccessState,
  NgramAccessError,
} from "@/lib/ngram2/access";
import { createSupabaseRouteClient, createSupabaseServiceClient } from "@/lib/supabase/serverClient";

export async function GET() {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  try {
    const service = createSupabaseServiceClient();
    const accessState = await getNgram2AccessState(service, user.id);
    const payload = await listAccessibleNgram2Summaries(service, accessState);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed to load N-Gram 2.0 access" },
      { status: error instanceof NgramAccessError ? error.status : 500 },
    );
  }
}
