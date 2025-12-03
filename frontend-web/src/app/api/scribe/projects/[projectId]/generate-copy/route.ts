import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import { processCopyJob } from "@/lib/scribe/jobProcessor";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

interface GenerateCopyPayload {
  skuIds?: string[];
  mode?: "all" | "sample";
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
    return NextResponse.json(
      { error: { code: "unauthorized", message: "Unauthorized" } },
      { status: 401 },
    );
  }

  // Parse request body
  const body = (await request.json()) as GenerateCopyPayload;
  const { skuIds, mode = "all" } = body;

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

  // Get target SKUs
  let targetSkus: { id: string }[] = [];

  if (mode === "sample" && skuIds && skuIds.length > 0) {
    // Use first SKU if mode is sample
    const { data: sku, error: skuError } = await supabase
      .from("scribe_skus")
      .select("id")
      .eq("id", skuIds[0])
      .eq("project_id", projectId)
      .single();

    if (skuError || !sku) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "Sample SKU not found" } },
        { status: 400 },
      );
    }
    targetSkus = [sku];
  } else if (skuIds && skuIds.length > 0) {
    // Use provided SKU IDs
    const { data: skus, error: skusError } = await supabase
      .from("scribe_skus")
      .select("id")
      .eq("project_id", projectId)
      .in("id", skuIds);

    if (skusError || !skus || skus.length === 0) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "No valid SKUs found" } },
        { status: 400 },
      );
    }
    targetSkus = skus;
  } else {
    // Generate for all SKUs
    const { data: skus, error: skusError } = await supabase
      .from("scribe_skus")
      .select("id")
      .eq("project_id", projectId);

    if (skusError || !skus || skus.length === 0) {
      return NextResponse.json(
        { error: { code: "validation_error", message: "No SKUs found in project" } },
        { status: 400 },
      );
    }
    targetSkus = skus;
  }

  // Validate each target SKU has 5 selected topics
  for (const sku of targetSkus) {
    const { count, error: countError } = await supabase
      .from("scribe_topics")
      .select("*", { count: "exact", head: true })
      .eq("sku_id", sku.id)
      .eq("selected", true);

    if (countError) {
      return NextResponse.json(
        { error: { code: "server_error", message: countError.message } },
        { status: 500 },
      );
    }

    if ((count ?? 0) !== 5) {
      return NextResponse.json(
        {
          error: {
            code: "validation_error",
            message: "All target SKUs must have exactly 5 selected topics before generating copy",
          },
        },
        { status: 400 },
      );
    }
  }

  // Create job
  const { data: job, error: jobError } = await supabase
    .from("scribe_generation_jobs")
    .insert({
      project_id: projectId,
      job_type: "copy",
      status: "queued",
      payload: {
        projectId,
        skuIds: targetSkus.map((s) => s.id),
        jobType: "copy",
        options: {},
      },
    })
    .select("id")
    .single();

  if (jobError || !job) {
    return NextResponse.json(
      { error: { code: "server_error", message: jobError?.message ?? "Failed to create job" } },
      { status: 500 },
    );
  }

  // Trigger job processing asynchronously
  void processCopyJob(job.id).catch((error) => {
    console.error(`Background job processing failed for job ${job.id}:`, error);
  });

  return NextResponse.json({ jobId: job.id });
}
