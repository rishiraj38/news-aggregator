"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { Check, Layers, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ALLOWED_TOPIC_IDS,
  canonicalTopicSelection,
  HELIX_TOPIC_PACKS,
  type TopicId,
} from "@/lib/topics";

type Props = {
  initialTopics: string[];
  disabled?: boolean;
};

function normalizeInitial(raw: string[]): TopicId[] {
  return canonicalTopicSelection(raw);
}

export default function TopicBundlePicker({ initialTopics, disabled = false }: Props) {
  const router = useRouter();
  const [selected, setSelected] = useState<TopicId[]>(() => normalizeInitial(initialTopics));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const dirty = useMemo(() => {
    const a = [...selected].sort().join(",");
    const b = [...normalizeInitial(initialTopics)].sort().join(",");
    return a !== b;
  }, [selected, initialTopics]);

  const toggle = useCallback((id: TopicId) => {
    setMessage(null);
    setSelected((prev) => {
      if (prev.includes(id)) {
        if (prev.length === 1) return prev;
        return prev.filter((x) => x !== id);
      }
      return [...prev, id];
    });
  }, []);

  const selectAll = useCallback(() => {
    setMessage(null);
    setSelected([...ALLOWED_TOPIC_IDS]);
  }, []);

  const save = useCallback(async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("/api/me/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topics: selected }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage({
          type: "err",
          text: typeof data.error === "string" ? data.error : "Could not save preferences",
        });
        return;
      }
      setMessage({ type: "ok", text: "Topic bundles saved. The overnight job will harvest matching sources." });
      router.refresh();
    } catch {
      setMessage({ type: "err", text: "Network error — try again." });
    } finally {
      setSaving(false);
    }
  }, [selected, router]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-faint mb-1">
          Topic bundles
        </h2>
        <p className="text-sm text-ink-muted leading-relaxed max-w-xl">
          Each bundle maps to curated RSS + lab feeds. Selecting <span className="text-ink">two or more</span>
          lanes tells the curator to <span className="text-ink font-medium">interleave</span> top headlines so one
          section never dominates your send. Use <strong className="text-ink font-medium">Mix everything</strong>{" "}
          for the widest cross-topic briefing ({ALLOWED_TOPIC_IDS.length} bundles).
        </p>
      </div>

      <div className="flex flex-wrap gap-2 pb-1">
        <button
          type="button"
          disabled={disabled}
          onClick={selectAll}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border border-accent/35 bg-accent-soft/60 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink hover:bg-accent-soft transition-colors",
            disabled && "opacity-45 pointer-events-none",
          )}
        >
          <Layers className="w-3.5 h-3.5" strokeWidth={2} aria-hidden />
          Mix everything
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {HELIX_TOPIC_PACKS.map((pack) => {
          const on = selected.includes(pack.id);
          return (
            <button
              key={pack.id}
              type="button"
              disabled={disabled}
              onClick={() => toggle(pack.id)}
              className={cn(
                "text-left rounded-xl border px-4 py-3 transition-[border-color,background-color] min-h-[5.25rem]",
                on
                  ? "border-accent/45 bg-accent-soft/90"
                  : "border-line bg-surface-raised/80 hover:border-line-strong",
                disabled && "opacity-60 pointer-events-none",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-ink text-sm">{pack.label}</span>
                <span
                  className={cn(
                    "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border",
                    on ? "border-accent bg-accent text-surface-deep" : "border-line text-transparent",
                  )}
                  aria-hidden
                >
                  <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
                </span>
              </div>
              <p className="text-xs text-ink-muted mt-2 leading-relaxed">{pack.hint}</p>
            </button>
          );
        })}
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <button
          type="button"
          disabled={disabled || saving || !dirty}
          onClick={() => save()}
          className="inline-flex items-center justify-center gap-2 min-h-11 px-5 rounded-xl bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 disabled:opacity-45 disabled:pointer-events-none transition-[filter]"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Save topic bundles
        </button>
        {!dirty && (
          <span className="text-xs text-ink-faint">No pending changes.</span>
        )}
        {message && (
          <p
            className={cn(
              "text-sm",
              message.type === "ok" ? "text-emerald-400/90" : "text-rose-400/95",
            )}
          >
            {message.text}
          </p>
        )}
      </div>
    </div>
  );
}
