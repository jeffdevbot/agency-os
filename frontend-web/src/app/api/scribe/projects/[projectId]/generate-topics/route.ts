import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { processTopicsJob } from "@/lib/scribe/jobProcessor";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface GenerateTopicsPayload {
  skuIds?: string[] | null;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId?: string }> },
) {
  const { projectId } = await context.params;
  if (!isUuid(projectId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid project id" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  // Parse request body
  let payload: GenerateTopicsPayload = {};
  try {
    payload = (await request.json()) as GenerateTopicsPayload;
  } catch {
    // Empty body is fine - will use all SKUs
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

  // Only prevent generation on archived projects
  if (project.status === "archived") {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Archived projects are read-only" } },
      { status: 403 },
    );
  }

  // Get SKU IDs (either from payload or all SKUs in project)
  let skuIds: string[] = [];
  if (payload.skuIds && payload.skuIds.length > 0) {
    // Validate provided SKU IDs
    if (!payload.skuIds.every(isUuid)) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "invalid SKU ID(s)" } },
        { status: 400 },
      );
    }
    skuIds = payload.skuIds;
  } else {
    // Get all SKU IDs for this project
    const { data: skus, error: skusError } = await supabase
      .from("scribe_skus")
      .select("id")
      .eq("project_id", projectId);

    if (skusError) {
      return NextResponse.json(
        { error: { code: "server_error", message: skusError.message } },
        { status: 500 },
      );
    }

    if (!skus || skus.length === 0) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "No SKUs found in project" } },
        { status: 400 },
      );
    }

    skuIds = skus.map((sku) => sku.id);
  }

  // Create generation job
  const jobPayload = {
    projectId,
    skuIds,
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
  });

  return NextResponse.json({ jobId: job.id });
}
