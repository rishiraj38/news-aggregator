import { NextResponse } from "next/server";
import { db as prisma } from "@/lib/db";
import { requireAdmin } from "@/lib/admin-auth";

export async function GET() {
  // Admin only. The run log names every subscriber and their email address, so
  // a signed-in check is not enough — the dashboard used to hide this panel from
  // non-admins while the endpoint answered any account.
  const gate = await requireAdmin();
  if (!gate.ok) return gate.response;

  try {
    // Fetch the latest pipeline run
    const latestRun = await prisma.pipelineRun.findFirst({
      orderBy: {
        start_time: "desc",
      },
    });

    if (!latestRun) {
      return NextResponse.json({
        status: "IDLE",
        message: "No runs recorded yet.",
      });
    }

    // Return in the same format the frontend expects
    return NextResponse.json({
      id: latestRun.id,
      status: latestRun.status,
      start_time: latestRun.start_time,
      end_time: latestRun.end_time,
      log_summary: latestRun.log_summary,
      users_processed: latestRun.users_processed,
    });
  } catch (error) {
    console.error("Error fetching pipeline status:", error);
    return NextResponse.json(
      { error: "Failed to fetch pipeline status" },
      { status: 500 },
    );
  }
}
