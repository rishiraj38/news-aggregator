"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Loader2, RefreshCw, Save, Search, Undo2 } from "lucide-react";
import type { AdminMember, AdminTotals } from "@/lib/admin-types";
import {
  ALLOWED_STATUSES,
  ALLOWED_TIERS,
  isTrialExempt,
  TIER_LABELS,
  type Tier,
} from "@/lib/entitlements";
import { cn } from "@/lib/utils";
import { formatWhen, kindLabel, PanelMessage, StatusPill, TierBadge } from "./AdminBits";
import MemberDetail from "./MemberDetail";
import { useAdminJson } from "./useAdminJson";

type MembersResponse = { members: AdminMember[]; totals: AdminTotals; stats_window_days: number };

/** Unsaved edits for one member — only the fields that differ from what's saved. */
type Draft = { tier?: Tier; subscription_status?: string; is_active?: boolean };

const selectClass =
  "min-h-9 rounded-lg border border-line bg-surface-raised px-2 text-xs text-ink focus:border-accent/45 focus:outline-none disabled:opacity-45 cursor-pointer";
const changedRing = "ring-2 ring-accent/60 border-accent/60";

function describeChange(m: AdminMember, d: Draft): string {
  const parts: string[] = [];
  if (d.tier !== undefined) parts.push(`${TIER_LABELS[m.tier]} → ${TIER_LABELS[d.tier]}`);
  if (d.subscription_status !== undefined) parts.push(`${m.subscription_status} → ${d.subscription_status}`);
  if (d.is_active !== undefined) parts.push(d.is_active ? "resume emails" : "pause emails");
  return `• ${m.name} (${m.email}): ${parts.join(", ")}`;
}

export default function MembersPanel({ currentAdminId }: { currentAdminId: string }) {
  const { data, error, loading, reload } = useAdminJson<MembersResponse>("/api/admin/members");

  // Saved server values layered over the fetched list, so a successful save shows
  // immediately without refetching. Cleared on Refresh.
  const [overrides, setOverrides] = useState<Record<string, Partial<AdminMember>>>({});
  // Staged edits. Nothing reaches the server until "Save changes".
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [savingAll, setSavingAll] = useState(false);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const baseMembers = useMemo(
    () => (data?.members ?? []).map((m) => ({ ...m, ...overrides[m.id] })),
    [data, overrides],
  );

  const visibleMembers = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? baseMembers.filter((m) => `${m.name} ${m.email}`.toLowerCase().includes(q)) : baseMembers;
  }, [baseMembers, query]);

  const dirtyCount = Object.keys(drafts).length;

  // Warn before a reload or navigation throws staged edits away.
  useEffect(() => {
    if (dirtyCount === 0) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirtyCount]);

  const clearRowError = (id: string) =>
    setRowErrors((e) => {
      if (!(id in e)) return e;
      const next = { ...e };
      delete next[id];
      return next;
    });

  /** Stage a change. Setting a field back to its saved value un-stages it. */
  const applyDraft = useCallback((m: AdminMember, patch: Draft) => {
    setSaveMessage(null);
    clearRowError(m.id);
    setDrafts((prev) => {
      const next: Draft = { ...(prev[m.id] ?? {}), ...patch };
      if (next.tier === m.tier) delete next.tier;
      if (next.subscription_status === m.subscription_status) delete next.subscription_status;
      if (next.is_active === m.is_active) delete next.is_active;
      const out = { ...prev };
      if (Object.keys(next).length === 0) delete out[m.id];
      else out[m.id] = next;
      return out;
    });
  }, []);

  const discardRow = useCallback((id: string) => {
    setDrafts((prev) => {
      const out = { ...prev };
      delete out[id];
      return out;
    });
    clearRowError(id);
  }, []);

  const discardAll = useCallback(() => {
    setDrafts({});
    setRowErrors({});
    setSaveMessage(null);
  }, []);

  const refresh = useCallback(() => {
    if (Object.keys(drafts).length > 0 && !window.confirm("Discard your unsaved changes and reload?")) return;
    setDrafts({});
    setOverrides({});
    setRowErrors({});
    setSaveMessage(null);
    reload();
  }, [drafts, reload]);

  const saveAll = useCallback(async () => {
    const byId = new Map(baseMembers.map((m) => [m.id, m]));
    const entries = Object.entries(drafts)
      .map(([id, d]) => ({ m: byId.get(id), d }))
      .filter((e): e is { m: AdminMember; d: Draft } => Boolean(e.m));
    if (entries.length === 0) return;

    const grants = entries.some(({ m, d }) => d.tier === "admin" && m.tier !== "admin");
    const revokes = entries.some(({ m, d }) => d.tier !== undefined && d.tier !== "admin" && m.tier === "admin");
    const warnings = [
      grants && "⚠ This grants admin access: they'll see every member and can change anyone's plan.",
      revokes && "⚠ This removes admin access.",
    ].filter(Boolean);

    const summary = [
      `Save ${entries.length} change${entries.length === 1 ? "" : "s"}?`,
      "",
      ...entries.map(({ m, d }) => describeChange(m, d)),
      ...(warnings.length ? ["", ...warnings] : []),
    ].join("\n");
    if (!window.confirm(summary)) return;

    setSavingAll(true);
    setSaveMessage(null);
    let saved = 0;
    let failed = 0;

    // Sequential, so the server's last-admin check sees each change in turn.
    for (const { m, d } of entries) {
      try {
        const res = await fetch(`/api/admin/members/${encodeURIComponent(m.id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(d),
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          failed += 1;
          setRowErrors((e) => ({
            ...e,
            [m.id]: typeof json.error === "string" ? json.error : "Update failed",
          }));
          continue;
        }
        const u = json.member as AdminMember;
        setOverrides((o) => ({
          ...o,
          [m.id]: {
            role: u.role,
            plan: u.plan,
            tier: u.tier,
            subscription_status: u.subscription_status,
            is_active: u.is_active,
            trial_exempt: u.trial_exempt,
          },
        }));
        setDrafts((prev) => {
          const out = { ...prev };
          delete out[m.id];
          return out;
        });
        saved += 1;
      } catch {
        failed += 1;
        setRowErrors((e) => ({ ...e, [m.id]: "Network error — try again." }));
      }
    }

    setSavingAll(false);
    setSaveMessage(
      failed
        ? { type: "err", text: `Saved ${saved}, ${failed} failed — the highlighted rows still have unsaved changes.` }
        : { type: "ok", text: `Saved ${saved} change${saved === 1 ? "" : "s"}.` },
    );
  }, [baseMembers, drafts]);

  if (loading && !data) return <PanelMessage>Loading members…</PanelMessage>;
  if (error) return <PanelMessage tone="error">{error}</PanelMessage>;
  if (!data) return null;

  const { totals } = data;
  const cards: Array<[string, number]> = [
    ["Members", totals.total],
    ["Free", totals.free],
    ["Pro", totals.pro],
    ["Admins", totals.admin],
    ["Expired", totals.expired],
    ["Paused", totals.paused],
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2.5">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-xl border border-line bg-surface-raised/70 px-3 py-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink-faint">{label}</div>
            <div className="font-display text-2xl tabular-nums text-ink mt-1">{value}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
        <label className="relative flex-1">
          <span className="sr-only">Search members</span>
          <Search className="w-4 h-4 text-ink-faint absolute left-3 top-1/2 -translate-y-1/2" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name or email"
            className="w-full min-h-10 pl-9 pr-3 rounded-xl bg-surface-raised border border-line text-sm text-ink placeholder:text-ink-faint focus:border-accent/45 focus:outline-none"
          />
        </label>
        <button
          type="button"
          onClick={refresh}
          disabled={savingAll}
          className="inline-flex items-center justify-center gap-2 min-h-10 px-4 rounded-xl border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 disabled:opacity-45 transition-colors cursor-pointer"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} strokeWidth={2} />
          Refresh
        </button>
      </div>

      <p className="text-xs text-ink-faint">
        Changes are staged, not saved — edit as many members as you like, then press{" "}
        <span className="text-ink font-medium">Save changes</span>.
      </p>

      {saveMessage && (
        <p
          role="status"
          className={cn("text-sm", saveMessage.type === "ok" ? "text-emerald-300" : "text-rose-300")}
        >
          {saveMessage.text}
        </p>
      )}

      <div className="overflow-x-auto rounded-2xl border border-line">
        <table className="w-full min-w-[52rem] text-left text-sm">
          <thead className="bg-surface-raised/80 text-[10px] uppercase tracking-[0.16em] text-ink-faint">
            <tr>
              <th className="px-4 py-3 font-bold">Member</th>
              <th className="px-3 py-3 font-bold">Tier</th>
              <th className="px-3 py-3 font-bold">Subscription</th>
              <th className="px-3 py-3 font-bold">Active</th>
              <th className="px-3 py-3 font-bold">Last email</th>
              <th className="px-3 py-3 font-bold text-right">{data.stats_window_days}d</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {visibleMembers.map((m) => {
              const d = drafts[m.id];
              const dirty = Boolean(d);
              const tier: Tier = d?.tier ?? m.tier;
              const status = d?.subscription_status ?? m.subscription_status;
              const active = d?.is_active ?? m.is_active;
              const exempt = isTrialExempt(
                tier === "admin" ? "admin" : "user",
                tier === "pro" ? "pro" : "free",
                status,
              );
              const isSelf = m.id === currentAdminId;
              const open = openId === m.id;

              return (
                <Fragment key={m.id}>
                  <tr
                    className={cn(
                      "border-t border-line align-top",
                      dirty && "bg-accent-soft/[0.08]",
                      !active && "opacity-60",
                    )}
                  >
                    <td className={cn("px-4 py-3", dirty && "border-l-2 border-l-accent")}>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-ink">{m.name}</span>
                        <TierBadge tier={m.tier} />
                        {isSelf && <span className="text-[10px] text-ink-faint">(you)</span>}
                      </div>
                      <div className="text-xs text-ink-faint break-all">{m.email}</div>
                      {dirty && (
                        <div className="mt-1.5 flex items-center gap-2">
                          <span className="rounded-full border border-accent/45 bg-accent-soft px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink">
                            Unsaved
                          </span>
                          <button
                            type="button"
                            onClick={() => discardRow(m.id)}
                            disabled={savingAll}
                            className="inline-flex items-center gap-1 text-[11px] text-ink-muted hover:text-ink cursor-pointer disabled:opacity-45"
                          >
                            <Undo2 className="w-3 h-3" strokeWidth={2} aria-hidden />
                            Undo
                          </button>
                        </div>
                      )}
                      {rowErrors[m.id] && <div className="mt-1 text-xs text-rose-300">{rowErrors[m.id]}</div>}
                    </td>
                    <td className="px-3 py-3">
                      <select
                        aria-label={`Tier for ${m.email}`}
                        className={cn(selectClass, d?.tier !== undefined && changedRing)}
                        value={tier}
                        disabled={savingAll || isSelf}
                        title={isSelf ? "You can't change your own tier" : undefined}
                        onChange={(e) => applyDraft(m, { tier: e.target.value as Tier })}
                      >
                        {ALLOWED_TIERS.map((t) => (
                          <option key={t} value={t}>
                            {TIER_LABELS[t]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      <select
                        aria-label={`Subscription status for ${m.email}`}
                        className={cn(selectClass, d?.subscription_status !== undefined && changedRing)}
                        value={status}
                        disabled={savingAll}
                        onChange={(e) => applyDraft(m, { subscription_status: e.target.value })}
                      >
                        {ALLOWED_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <div className="mt-1 text-[10px] text-ink-faint">
                        {exempt ? "won't expire" : "on 27-day trial clock"}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={active}
                        aria-label={`${active ? "Pause" : "Resume"} emails for ${m.email}`}
                        disabled={savingAll || isSelf}
                        title={isSelf ? "You can't pause your own account" : undefined}
                        onClick={() => applyDraft(m, { is_active: !active })}
                        className={cn(
                          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed",
                          active ? "bg-emerald-500/70 border-emerald-400/50" : "bg-surface-deep border-line-strong",
                          d?.is_active !== undefined && "ring-2 ring-accent/60",
                        )}
                      >
                        <span
                          className={cn(
                            "inline-block h-4 w-4 rounded-full bg-white transition-transform",
                            active ? "translate-x-6" : "translate-x-1",
                          )}
                        />
                      </button>
                    </td>
                    <td className="px-3 py-3">
                      {m.last_delivery ? (
                        <div className="space-y-1">
                          <StatusPill status={m.last_delivery.status} />
                          <div className="text-xs text-ink-muted">{kindLabel(m.last_delivery.kind)}</div>
                          <div className="text-[11px] text-ink-faint">{formatWhen(m.last_delivery.sent_at)}</div>
                        </div>
                      ) : (
                        <span className="text-xs text-ink-faint">None logged</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-xs">
                      <div className="text-emerald-300">{m.sent_30d} sent</div>
                      <div className={m.failed_30d ? "text-rose-300" : "text-ink-faint"}>{m.failed_30d} failed</div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <button
                        type="button"
                        aria-expanded={open}
                        onClick={() => setOpenId(open ? null : m.id)}
                        className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-ink-muted hover:text-ink hover:bg-surface-raised transition-colors cursor-pointer"
                      >
                        Details
                        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
                      </button>
                    </td>
                  </tr>
                  {open && (
                    <tr className="border-t border-line bg-surface/60">
                      <td colSpan={7} className="px-4 py-5">
                        <MemberDetail key={m.id} memberId={m.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {visibleMembers.length === 0 && <PanelMessage>No members match &ldquo;{query}&rdquo;.</PanelMessage>}
      </div>

      {dirtyCount > 0 && (
        <div className="sticky bottom-4 z-20">
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-2xl border border-accent/45 bg-surface-deep/95 backdrop-blur-md px-4 py-3 shadow-[0_24px_60px_-28px_rgb(0_0_0/0.9)]">
            <p className="flex-1 text-sm text-ink">
              <span className="font-semibold tabular-nums">{dirtyCount}</span> member
              {dirtyCount === 1 ? "" : "s"} with unsaved changes
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={discardAll}
                disabled={savingAll}
                className="inline-flex flex-1 sm:flex-none items-center justify-center min-h-10 px-4 rounded-xl border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 disabled:opacity-45 transition-colors cursor-pointer"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={saveAll}
                disabled={savingAll}
                className="inline-flex flex-1 sm:flex-none items-center justify-center gap-2 min-h-10 px-5 rounded-xl bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 disabled:opacity-60 transition-[filter] cursor-pointer"
              >
                {savingAll ? (
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                ) : (
                  <Save className="w-4 h-4" strokeWidth={2} aria-hidden />
                )}
                {savingAll ? "Saving…" : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
