"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useRef, useState } from "react";
import { Loader2, Plus, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  canonicalKeywordSelection,
  MAX_KEYWORD_CHARS,
  MAX_KEYWORDS_PER_USER,
  normalizeKeyword,
} from "@/lib/topics";

type Props = {
  initialKeywords: string[];
  /** Locked for non-admin trial users; chips stay visible but read-only. */
  disabled?: boolean;
  lockedHint?: string;
};

export default function KeywordManager({
  initialKeywords,
  disabled = false,
  lockedHint,
}: Props) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const initial = useMemo(
    () => canonicalKeywordSelection(initialKeywords),
    [initialKeywords],
  );

  const [keywords, setKeywords] = useState<string[]>(initial);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const dirty = useMemo(
    () => JSON.stringify(keywords) !== JSON.stringify(initial),
    [keywords, initial],
  );
  const atCap = keywords.length >= MAX_KEYWORDS_PER_USER;

  const add = useCallback(() => {
    const kw = normalizeKeyword(draft);
    if (!kw) {
      setMessage({ type: "err", text: "Keywords need at least 2 characters." });
      return;
    }
    if (keywords.includes(kw)) {
      setMessage({ type: "err", text: `"${kw}" is already tracked.` });
      setDraft("");
      return;
    }
    if (keywords.length >= MAX_KEYWORDS_PER_USER) {
      setMessage({
        type: "err",
        text: `You can track up to ${MAX_KEYWORDS_PER_USER} keywords.`,
      });
      return;
    }
    setMessage(null);
    setKeywords((prev) => [...prev, kw]);
    setDraft("");
    inputRef.current?.focus();
  }, [draft, keywords]);

  const remove = useCallback((kw: string) => {
    setMessage(null);
    setKeywords((prev) => prev.filter((k) => k !== kw));
  }, []);

  const save = useCallback(async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("/api/me/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keywords }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage({
          type: "err",
          text: typeof data.error === "string" ? data.error : "Could not save keywords",
        });
        return;
      }
      setKeywords(Array.isArray(data.keywords) ? data.keywords : keywords);
      setMessage({
        type: "ok",
        text: keywords.length
          ? "Keywords saved. Tomorrow's run will search news and Hacker News for each one."
          : "Keywords cleared.",
      });
      router.refresh();
    } catch {
      setMessage({ type: "err", text: "Network error — try again." });
    } finally {
      setSaving(false);
    }
  }, [keywords, router]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-faint mb-1">
          Tracked keywords
        </h2>
        <p className="text-sm text-ink-muted leading-relaxed max-w-xl">
          Anything topic bundles miss. Each keyword gets its own nightly search across
          news and Hacker News, and matches are{" "}
          <span className="text-ink font-medium">reserved a share of your digest</span>{" "}
          so they never get crowded out. Up to {MAX_KEYWORDS_PER_USER} terms.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {keywords.length === 0 && (
          <span className="text-sm text-ink-faint">
            No keywords yet — add one below to start tracking it.
          </span>
        )}
        {keywords.map((kw) => (
          <span
            key={kw}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface-raised/95 text-[0.9rem] text-ink-muted border border-line/90"
          >
            {kw}
            {!disabled && (
              <button
                type="button"
                onClick={() => remove(kw)}
                aria-label={`Remove keyword ${kw}`}
                className="text-ink-faint hover:text-rose-300 transition-colors cursor-pointer"
              >
                <X className="w-3.5 h-3.5" strokeWidth={2.5} />
              </button>
            )}
          </span>
        ))}
      </div>

      {disabled ? (
        <p className="text-[11px] text-ink-faint">
          {lockedHint || "Upgrade to track your own keywords."}
        </p>
      ) : (
        <>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              ref={inputRef}
              type="text"
              value={draft}
              maxLength={MAX_KEYWORD_CHARS}
              disabled={atCap}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  add();
                }
              }}
              placeholder={
                atCap ? `Limit of ${MAX_KEYWORDS_PER_USER} reached` : 'e.g. "ai agents"'
              }
              className="flex-1 min-h-11 px-4 rounded-xl bg-surface-raised border border-line text-sm text-ink placeholder:text-ink-faint focus:border-accent/45 focus:outline-none disabled:opacity-50"
            />
            <button
              type="button"
              onClick={add}
              disabled={atCap || !draft.trim()}
              className="inline-flex items-center justify-center gap-2 min-h-11 px-5 rounded-xl border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 disabled:opacity-45 disabled:pointer-events-none cursor-pointer transition-colors"
            >
              <Plus className="w-4 h-4" strokeWidth={2} />
              Add
            </button>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <button
              type="button"
              disabled={saving || !dirty}
              onClick={() => save()}
              className="inline-flex items-center justify-center gap-2 min-h-11 px-5 rounded-xl bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 disabled:opacity-45 disabled:pointer-events-none disabled:cursor-not-allowed cursor-pointer transition-[filter]"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" strokeWidth={2} />
              )}
              Save keywords
            </button>
            {!dirty && <span className="text-xs text-ink-faint">No pending changes.</span>}
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
        </>
      )}
    </div>
  );
}
