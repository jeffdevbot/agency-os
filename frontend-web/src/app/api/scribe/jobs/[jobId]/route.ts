import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ jobId?: string }> },
) {
  const { jobId } = await context.params;
  if (!isUuid(jobId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid job id" } },
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

  // Fetch job
  const { data: job, error } = await supabase
    .from("scribe_generation_jobs")
    .select("id, project_id, job_type, status, payload, error_message, created_at, completed_at")
    .eq("id", jobId)
    .single();

  if (error || !job) {
    const status = error?.code === "PGRST116" ? 404 : 500;
    return NextResponse.json(
      { error: { code: "not_found", message: error?.message ?? "Job not found" } },
      { status },
    );
  }

  // Verify the job belongs to a project owned by the user
  const { data: project, error: projectError } = await supabase
    .from("scribe_projects")
    .select("id")
    .eq("id", job.project_id)
    .eq("created_by", session.user.id)
    .single();

  if (projectError || !project) {
    return NextResponse.json(
      { error: { code: "forbidden", message: "Forbidden" } },
      { status: 403 },
    );
  }

  return NextResponse.json({
    id: job.id,
    projectId: job.project_id,
    jobType: job.job_type,
    status: job.status,
    payload: job.payload,
    errorMessage: job.error_message,
    createdAt: job.created_at,
    completedAt: job.completed_at,
  });
}
