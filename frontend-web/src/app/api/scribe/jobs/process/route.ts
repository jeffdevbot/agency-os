import { NextResponse } from "next/server";
import { createSupabaseServiceClient } from "@/lib/supabase/serverClient";
import { processTopicsJob } from "@/lib/scribe/jobProcessor";

/**
 * Job processor endpoint
 * This endpoint processes queued Scribe generation jobs
 * Can be called manually or by a cron job
 */
export async function POST() {
  const supabase = createSupabaseServiceClient();

  try {
    // Fetch all queued jobs
    const { data: queuedJobs, error: fetchError } = await supabase
      .from("scribe_generation_jobs")
      .select("id, job_type")
      .eq("status", "queued")
      .order("created_at", { ascending: true })
      .limit(10); // Process up to 10 jobs at a time

    if (fetchError) {
      return NextResponse.json(
        { error: { code: "server_error", message: fetchError.message } },
        { status: 500 },
      );
    }

    if (!queuedJobs || queuedJobs.length === 0) {
      return NextResponse.json({ message: "No queued jobs", processed: 0 });
    }

    const results = [];

    // Process each job
    for (const job of queuedJobs) {
      try {
        if (job.job_type === "topics") {
          await processTopicsJob(job.id);
          results.push({ jobId: job.id, status: "success" });
        } else {
          results.push({
            jobId: job.id,
            status: "skipped",
            reason: `Unknown job type: ${job.job_type}`,
          });
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        results.push({ jobId: job.id, status: "error", error: errorMessage });
        console.error(`Failed to process job ${job.id}:`, errorMessage);
      }
    }

    return NextResponse.json({
      message: "Job processing complete",
      processed: results.length,
      results,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: {
          code: "server_error",
          message: error instanceof Error ? error.message : "Job processing failed",
        },
      },
      { status: 500 },
    );
  }
}
