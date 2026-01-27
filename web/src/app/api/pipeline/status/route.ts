import { NextResponse } from "next/server";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

export async function GET() {
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
  } finally {
    await prisma.$disconnect();
  }
}
