/**
 * Subscriber tiers. Mirrors `app/services/entitlements.py` — keep them in step.
 *
 *  - admin  → everything, plus the admin console. `role` overrides `plan`.
 *  - pro    → full customization: topic bundles and keyword tracking.
 *  - free   → fixed briefing: every bundle, no keywords. The default.
 *
 * These checks gate the UI, but the API routes call them too. A disabled button
 * is not a permission check.
 */

export const ALLOWED_ROLES = ["user", "admin"] as const;
export const ALLOWED_PLANS = ["free", "pro"] as const;
export const ALLOWED_STATUSES = ["trial", "active", "expired"] as const;

export type Role = (typeof ALLOWED_ROLES)[number];
export type Plan = (typeof ALLOWED_PLANS)[number];
export type SubscriptionStatus = (typeof ALLOWED_STATUSES)[number];
export type Tier = "free" | "pro" | "admin";

export const TIER_LABELS: Record<Tier, string> = {
  free: "Free",
  pro: "Pro",
  admin: "Administrator",
};

function clean(raw: unknown): string {
  return typeof raw === "string" ? raw.trim().toLowerCase() : "";
}

/** Unknown or missing plans are Free — never accidentally Pro. */
export function normalizePlan(raw: unknown): Plan {
  return clean(raw) === "pro" ? "pro" : "free";
}

export function isAdminRole(role: unknown): boolean {
  return clean(role) === "admin";
}

export function effectiveTier(role: unknown, plan: unknown): Tier {
  if (isAdminRole(role)) return "admin";
  return normalizePlan(plan) === "pro" ? "pro" : "free";
}

export function canCustomize(role: unknown, plan: unknown): boolean {
  return effectiveTier(role, plan) !== "free";
}

export function canTrackKeywords(role: unknown, plan: unknown): boolean {
  return effectiveTier(role, plan) !== "free";
}

/**
 * Whether the pipeline's 27-day trial clock may expire this subscriber. An
 * admin-set `active` status counts, otherwise the next run would recompute
 * expiry from created_at and undo the change made in the console.
 */
export function isTrialExempt(role: unknown, plan: unknown, status: unknown): boolean {
  return effectiveTier(role, plan) !== "free" || clean(status) === "active";
}

export const ALLOWED_TIERS = ["free", "pro", "admin"] as const;

/**
 * The columns a tier maps to. Admin is decided by `role` alone, so promoting to
 * admin leaves `plan` untouched; moving to Free or Pro sets both.
 *
 * The admin console used to expose role and plan as separate controls. Setting
 * plan=pro on an admin saved correctly but changed nothing visible, because role
 * overrides plan — so it looked like the change had failed.
 */
export function tierToRolePlan(tier: Tier): { role: Role; plan?: Plan } {
  if (tier === "admin") return { role: "admin" };
  return { role: "user", plan: tier };
}

export function isAllowed<T extends string>(allowed: readonly T[], value: unknown): value is T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value);
}
