"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { CheckCircle2, Loader2, Sparkles } from "lucide-react";

// Fixed locale and time zone so the server render and client hydration agree.
const dateFormat = new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" });

export default function UpgradeRequestButton({ initialRequestedAt }: { initialRequestedAt: string | null }) {
  const router = useRouter();
  const [requestedAt, setRequestedAt] = useState(initialRequestedAt);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(method: "POST" | "DELETE") {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/me/upgrade-request", { method });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(typeof json.error === "string" ? json.error : "Something went wrong — try again.");
        return;
      }
      setRequestedAt(method === "POST" ? (json.requested_at ?? new Date().toISOString()) : null);
      router.refresh();
    } catch {
      setError("Network error — try again.");
    } finally {
      setBusy(false);
    }
  }

  if (requestedAt) {
    return (
      <div className="space-y-3">
        <p className="flex items-start gap-2 text-sm text-emerald-300" role="status">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={2} aria-hidden />
          <span>
            Request sent on {dateFormat.format(new Date(requestedAt))}. An admin will review it, and Pro unlocks on
            your dashboard as soon as it&rsquo;s approved.
          </span>
        </p>
        <button
          type="button"
          onClick={() => send("DELETE")}
          disabled={busy}
          className="text-xs text-ink-muted underline underline-offset-4 hover:text-ink disabled:opacity-45 cursor-pointer"
        >
          {busy ? "Cancelling…" : "Cancel request"}
        </button>
        {error && <p className="text-sm text-rose-400/95">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => send("POST")}
        disabled={busy}
        className="inline-flex items-center justify-center gap-2 min-h-11 px-6 rounded-xl bg-violet-500 text-white text-sm font-semibold hover:brightness-110 disabled:opacity-60 transition-[filter] cursor-pointer"
      >
        {busy ? (
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
        ) : (
          <Sparkles className="w-4 h-4" strokeWidth={2} aria-hidden />
        )}
        {busy ? "Sending…" : "Request Pro access"}
      </button>
      {error && <p className="text-sm text-rose-400/95">{error}</p>}
    </div>
  );
}
