"use client";

import { useState, useEffect } from "react";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Clock,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

type PipelineStatusRecord = {
  id: string;
  status: string;
  start_time: string;
  end_time: string | null;
  log_summary: string;
  users_processed: string;
};

export function PipelineStatus() {
  const [status, setStatus] = useState<PipelineStatusRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/pipeline/status");
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
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !status)
    return (
      <div className="rounded-lg border border-line bg-surface p-8 flex items-center justify-center gap-3 text-ink-muted">
        <Loader2 className="w-5 h-5 animate-spin text-accent shrink-0" />
        <span className="text-sm">Checking pipeline…</span>
      </div>
    );

  if (error)
    return (
      <div className="rounded-lg border border-red-900/50 bg-red-950/25 px-5 py-4 text-red-200/95">
        <h3 className="font-semibold flex items-center gap-2 text-sm">
          <XCircle className="w-4 h-4 shrink-0 text-red-400" strokeWidth={2} />
          Pipeline unreachable
        </h3>
        <p className="text-xs text-red-200/70 mt-2 leading-relaxed">{error}</p>
      </div>
    );

  const isRunning = status?.status === "RUNNING";
  const isSuccess = status?.status === "SUCCESS";
  const isFailed = status?.status === "FAILED";
  const isIdle = status?.status === "IDLE";

  const badgeStyles = cn(
    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border",
    isRunning && "border-blue-500/35 bg-blue-500/10 text-blue-200",
    isSuccess && "border-emerald-500/35 bg-emerald-500/10 text-emerald-200",
    isFailed && "border-red-500/35 bg-red-500/10 text-red-200",
    isIdle && "border-line-strong bg-surface-raised text-ink-muted",
  );

  return (
    <div className="rounded-lg border border-line bg-surface overflow-hidden">
      <div className="px-5 py-4 sm:px-6 sm:py-5 border-b border-line flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-lg tracking-tight flex items-center gap-2">
          <Activity className="w-5 h-5 text-accent shrink-0" strokeWidth={1.75} />
          System status
          {isRunning && (
            <span className="flex h-2 w-2 rounded-full bg-blue-400 animate-pulse" aria-hidden />
          )}
        </h3>
        <span className={badgeStyles}>
          {isRunning && <RefreshCw className="w-3 h-3 animate-spin shrink-0" strokeWidth={2} />}
          {isSuccess && <CheckCircle2 className="w-3 h-3 shrink-0 text-emerald-400" strokeWidth={2} />}
          {isFailed && <XCircle className="w-3 h-3 shrink-0 text-red-400" strokeWidth={2} />}
          {status?.status ?? "UNKNOWN"}
        </span>
      </div>

      <div className="px-5 py-5 sm:px-6 sm:pb-6 space-y-5">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-ink-faint block text-xs uppercase tracking-wider mb-1">
              Users processed
            </span>
            <span className="font-semibold tabular-nums text-ink">{status?.users_processed ?? "—"}</span>
          </div>
          <div>
            <span className="text-ink-faint block text-xs uppercase tracking-wider mb-1">
              Last run
            </span>
            <span className="font-medium text-ink-muted text-[0.8125rem] leading-snug">
              {status?.start_time
                ? new Date(status.start_time).toLocaleString()
                : "Never"}
            </span>
          </div>
        </div>

        <div className="rounded-md bg-surface-deep border border-line p-3 font-mono text-[0.75rem] leading-relaxed text-ink-muted h-44 sm:h-48 overflow-y-auto whitespace-pre-wrap">
          {status?.log_summary || "No logs yet."}
        </div>

        {isRunning && (
          <p className="text-xs text-center text-ink-faint animate-pulse">
            Live refresh every 5s
          </p>
        )}

        {!isRunning && (
          <div className="pt-4 border-t border-line flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs text-ink-faint">
            <span>Idle — awaiting scheduler</span>
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 shrink-0 text-accent/80" strokeWidth={2} />
              Next run per cron configuration
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
