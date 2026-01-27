"use client";

import { useState, useEffect } from "react";
import { Loader2, CheckCircle2, XCircle, RefreshCw, Clock } from "lucide-react";

type PipelineStatus = {
  id: string;
  status: string;
  start_time: string;
  end_time: string | null;
  log_summary: string;
  users_processed: string;
};

export function PipelineStatus() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const API_URL = ""; // Use local Next.js API route

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/pipeline/status`);
      if (!res.ok) throw new Error("Failed to fetch status");
      const data = await res.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError("Could not connect to pipeline service");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchStatus();

    // Poll every 5 seconds
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !status)
    return (
      <div className="p-4 rounded-xl border bg-card text-card-foreground shadow-sm animate-pulse h-32">
        <Loader2 />
      </div>
    );

  if (error)
    return (
      <div className="p-4 rounded-xl border border-red-200 bg-red-50 text-red-700">
        <h3 className="font-semibold flex items-center gap-2">
          <XCircle className="w-5 h-5" /> Pipeline Disconnected
        </h3>
        <p className="text-sm mt-1">{error}</p>
      </div>
    );

  const isRunning = status?.status === "RUNNING";
  const isSuccess = status?.status === "SUCCESS";
  const isFailed = status?.status === "FAILED";
  const isIdle = status?.status === "IDLE";

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
      <div className="p-6 pb-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            System Status
            {isRunning && (
              <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
            )}
          </h3>
          <div
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium border flex items-center gap-1
                        ${isRunning ? "bg-blue-100 text-blue-700 border-blue-200" : ""}
                        ${isSuccess ? "bg-green-100 text-green-700 border-green-200" : ""}
                        ${isFailed ? "bg-red-100 text-red-700 border-red-200" : ""}
                        ${isIdle ? "bg-gray-100 text-gray-600 border-gray-200" : ""}
                    `}
          >
            {isRunning && <RefreshCw className="w-3 h-3 animate-spin" />}
            {isSuccess && <CheckCircle2 className="w-3 h-3" />}
            {isFailed && <XCircle className="w-3 h-3" />}
            {status?.status || "UNKNOWN"}
          </div>
        </div>
      </div>

      <div className="p-6 pt-2 space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground block text-xs">
              Users Processed
            </span>
            <span className="font-medium">{status?.users_processed || 0}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-xs">
              Last Run
            </span>
            <span className="font-medium">
              {status?.start_time
                ? new Date(status.start_time).toLocaleString()
                : "Never"}
            </span>
          </div>
        </div>

        {/* Log Window */}
        <div className="bg-zinc-950 rounded-lg p-3 font-mono text-xs text-zinc-300 h-48 overflow-y-auto whitespace-pre-wrap border border-zinc-800">
          {status?.log_summary || "No logs available..."}
        </div>

        {isRunning && (
          <p className="text-xs text-center text-muted-foreground animate-pulse">
            Pipeline is active. Refreshing live...
          </p>
        )}

        {!isRunning && (
          <div className="mt-4 pt-3 border-t border-zinc-800 flex items-center justify-between text-xs text-muted-foreground">
            <span>Status: System Idle</span>
            <span className="flex items-center gap-1.5">
              <Clock className="w-3 h-3" />
              Next Scheduled Run: Today at 7:00 PM IST
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
