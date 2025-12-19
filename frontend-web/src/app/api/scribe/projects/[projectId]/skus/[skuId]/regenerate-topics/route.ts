import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { processTopicsJob } from "@/lib/scribe/jobProcessor";
import { logAppError } from "@/lib/ai/errorLogger";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string; skuId?: string }> },
) {
  const requestId = request.headers.get("x-request-id") ?? undefined;
  const route = new URL(request.url).pathname;
  let userId: string | undefined;
  let userEmail: string | undefined;

  try {
    const { projectId, skuId } = await context.params;

  if (!isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  if (!isUuid(skuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid SKU id" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  userId = session?.user?.id;
  userEmail = session?.user?.email;

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  // Fetch project and verify ownership
  const { data: project, error: fetchError } = await supabase
    .from("scribe_projects")
    .select("id, status, created_by")
    .eq("id", projectId)
    .eq("created_by", session.user.id)
    .single();

  if (fetchError || !project) {
    const status = fetchError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: fetchError?.message ?? "Project not found" } },
      { status },
    );
  }

  // Only prevent regeneration on archived projects
  if (project.status === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  // Verify SKU belongs to this project
  const { data: sku, error: skuError } = await supabase
    .from("scribe_skus")
    .select("id")
    .eq("id", skuId)
    .eq("project_id", projectId)
    .single();

  if (skuError || !sku) {
    const status = skuError?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: skuError?.message ?? "SKU not found" } },
      { status },
    );
  }

  // Create generation job for this single SKU
  const jobPayload = {
    projectId,
    skuIds: [skuId],
    jobType: "topics",
    options: {},
  };

  const { data: job, error: jobError } = await supabase
    .from("scribe_generation_jobs")
    .insert({
      project_id: projectId,
      job_type: "topics",
      status: "queued",
      payload: jobPayload,
      created_at: new Date().toISOString(),
    })
    .select("id")
    .single();

  if (jobError || !job) {
    return NextResponse.json(
      { error: { code: "server_error", message: jobError?.message ?? "Failed to create job" } },
      { status: 500 },
    );
  }

  // Trigger job processing asynchronously (don't await - let it run in background)
  void processTopicsJob(job.id).catch((error) => {
    console.error(`Background job processing failed for job ${job.id}:`, error);
    void logAppError({
      tool: "scribe",
      route,
      method: request.method,
      statusCode: 500,
      requestId,
      userId,
      userEmail,
      message: error instanceof Error ? error.message : String(error),
      meta: { jobId: job.id, projectId, skuId, stage: "stage_b", type: "background_job_failure" },
    });
  });

  return NextResponse.json({ jobId: job.id });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await logAppError({
      tool: "scribe",
      route,
      method: request.method,
      statusCode: 500,
      requestId,
      userId,
      userEmail,
      message,
      meta: { type: "route_error" },
    });
    return NextResponse.json(
      { error: { code: "server_error", message } },
      { status: 500 },
    );
  }
}
