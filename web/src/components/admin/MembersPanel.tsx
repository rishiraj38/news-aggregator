"use client";

import { Fragment, useCallback, useMemo, useState } from "react";
import { ChevronDown, RefreshCw, Search } from "lucide-react";
import type { AdminMember, AdminTotals, MemberPatch } from "@/lib/admin-types";
import { ALLOWED_PLANS, ALLOWED_ROLES, ALLOWED_STATUSES } from "@/lib/entitlements";
import { cn } from "@/lib/utils";
import { formatWhen, kindLabel, PanelMessage, StatusPill, TierBadge } from "./AdminBits";
import MemberDetail from "./MemberDetail";
import { useAdminJson } from "./useAdminJson";

type MembersResponse = { members: AdminMember[]; totals: AdminTotals; stats_window_days: number };

const selectClass =
  "min-h-9 rounded-lg border border-line bg-surface-raised px-2 text-xs text-ink focus:border-accent/45 focus:outline-none disabled:opacity-45 cursor-pointer";

export default function MembersPanel({ currentAdminId }: { currentAdminId: string }) {
  const { data, error, loading, reload } = useAdminJson<MembersResponse>("/api/admin/members");

  // Edits are layered over the fetched list rather than copied into state, so a
  // refresh is the single source of truth.
  const [overrides, setOverrides] = useState<Record<string, Partial<AdminMember>>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [openId, setOpenId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const members = useMemo(() => {
    const list = (data?.members ?? []).map((m) => ({ ...m, ...overrides[m.id] }));
    const q = query.trim().toLowerCase();
    return q ? list.filter((m) => `${m.name} ${m.email}`.toLowerCase().includes(q)) : list;
  }, [data, overrides, query]);

  const refresh = useCallback(() => {
    setOverrides({});
    setRowErrors({});
    reload();
  }, [reload]);

  const update = useCallback(async (member: AdminMember, patch: MemberPatch) => {
    if (patch.role === "admin" && member.role !== "admin") {
      const ok = window.confirm(
        `Make ${member.email} an administrator? They will be able to see every subscriber and change anyone's plan.`,
      );
      if (!ok) return;
    }

    setSavingId(member.id);
    setRowErrors((e) => {
      const next = { ...e };
      delete next[member.id];
      return next;
    });

    try {
      const res = await fetch(`/api/admin/members/${encodeURIComponent(member.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        setRowErrors((e) => ({
          ...e,
          [member.id]: typeof json.error === "string" ? json.error : "Update failed",
        }));
        return;
      }
      const u = json.member as AdminMember;
      setOverrides((o) => ({
        ...o,
        [member.id]: {
          role: u.role,
          plan: u.plan,
          tier: u.tier,
          subscription_status: u.subscription_status,
          is_active: u.is_active,
          trial_exempt: u.trial_exempt,
        },
      }));
    } catch {
      setRowErrors((e) => ({ ...e, [member.id]: "Network error — try again." }));
    } finally {
      setSavingId(null);
    }
  }, []);

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
          className="inline-flex items-center justify-center gap-2 min-h-10 px-4 rounded-xl border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 transition-colors cursor-pointer"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} strokeWidth={2} />
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-line">
        <table className="w-full min-w-[56rem] text-left text-sm">
          <thead className="bg-surface-raised/80 text-[10px] uppercase tracking-[0.16em] text-ink-faint">
            <tr>
              <th className="px-4 py-3 font-bold">Member</th>
              <th className="px-3 py-3 font-bold">Plan</th>
              <th className="px-3 py-3 font-bold">Subscription</th>
              <th className="px-3 py-3 font-bold">Role</th>
              <th className="px-3 py-3 font-bold">Active</th>
              <th className="px-3 py-3 font-bold">Last email</th>
              <th className="px-3 py-3 font-bold text-right">{data.stats_window_days}d</th>
              <th className="px-3 py-3" />
            </tr>
          </thead>
          <tbody>
            {members.map((m) => {
              const isSelf = m.id === currentAdminId;
              const busy = savingId === m.id;
              const open = openId === m.id;
              return (
                <Fragment key={m.id}>
                  <tr className={cn("border-t border-line align-top", !m.is_active && "opacity-60")}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-ink">{m.name}</span>
                        <TierBadge tier={m.tier} />
                        {isSelf && <span className="text-[10px] text-ink-faint">(you)</span>}
                      </div>
                      <div className="text-xs text-ink-faint break-all">{m.email}</div>
                      {rowErrors[m.id] && <div className="mt-1 text-xs text-rose-300">{rowErrors[m.id]}</div>}
                    </td>
                    <td className="px-3 py-3">
                      <select
                        aria-label={`Plan for ${m.email}`}
                        className={selectClass}
                        value={m.plan}
                        disabled={busy}
                        onChange={(e) => update(m, { plan: e.target.value })}
                      >
                        {ALLOWED_PLANS.map((p) => (
                          <option key={p} value={p}>
                            {p === "pro" ? "Pro" : "Free"}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      <select
                        aria-label={`Subscription status for ${m.email}`}
                        className={selectClass}
                        value={m.subscription_status}
                        disabled={busy}
                        onChange={(e) => update(m, { subscription_status: e.target.value })}
                      >
                        {ALLOWED_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                      <div className="mt-1 text-[10px] text-ink-faint">
                        {m.trial_exempt ? "won't expire" : "on trial clock"}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <select
                        aria-label={`Role for ${m.email}`}
                        className={selectClass}
                        value={m.role}
                        disabled={busy || isSelf}
                        title={isSelf ? "You can't change your own role" : undefined}
                        onChange={(e) => update(m, { role: e.target.value })}
                      >
                        {ALLOWED_ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={m.is_active}
                        aria-label={`${m.is_active ? "Pause" : "Resume"} emails for ${m.email}`}
                        disabled={busy || isSelf}
                        title={isSelf ? "You can't pause your own account" : undefined}
                        onClick={() => update(m, { is_active: !m.is_active })}
                        className={cn(
                          "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed",
                          m.is_active ? "bg-emerald-500/70 border-emerald-400/50" : "bg-surface-deep border-line-strong",
                        )}
                      >
                        <span
                          className={cn(
                            "inline-block h-4 w-4 rounded-full bg-white transition-transform",
                            m.is_active ? "translate-x-6" : "translate-x-1",
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
                      <td colSpan={8} className="px-4 py-5">
                        <MemberDetail key={m.id} memberId={m.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {members.length === 0 && <PanelMessage>No members match &ldquo;{query}&rdquo;.</PanelMessage>}
      </div>
    </div>
  );
}
