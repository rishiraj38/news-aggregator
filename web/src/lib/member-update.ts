import {
  ALLOWED_PLANS,
  ALLOWED_ROLES,
  ALLOWED_STATUSES,
  ALLOWED_TIERS,
  isAdminRole,
  isAllowed,
  tierToRolePlan,
} from "./entitlements";

/** Column updates for one member, in the database's string-boolean convention. */
export type MemberUpdateData = {
  plan?: string;
  role?: string;
  subscription_status?: string;
  is_active?: string;
};

export type MemberUpdatePlan =
  | { ok: true; data: MemberUpdateData }
  | { ok: false; status: 400 | 409; error: string };

/**
 * Validate an admin's requested change to one member and turn it into column
 * updates.
 *
 * Deliberately pure — no database access — so the guard rails can be tested
 * directly. The caller supplies `adminCount`, the current number of admins.
 *
 * Accepts `tier` (the console's single Free / Pro / Admin control), or the
 * lower-level `role` / `plan`, but not both in one request.
 */
export function planMemberUpdate(
  body: unknown,
  target: { id: string; role: string },
  actorId: string,
  adminCount: number,
): MemberUpdatePlan {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, status: 400, error: "Invalid body" };
  }
  const b = body as Record<string, unknown>;
  const has = (key: string) => Object.prototype.hasOwnProperty.call(b, key);
  const data: MemberUpdateData = {};

  if (has("tier") && (has("role") || has("plan"))) {
    return { ok: false, status: 400, error: "Send either tier, or role/plan — not both" };
  }

  if (has("tier")) {
    const tier = b.tier;
    if (!isAllowed(ALLOWED_TIERS, tier)) {
      return { ok: false, status: 400, error: `tier must be one of: ${ALLOWED_TIERS.join(", ")}` };
    }
    const mapped = tierToRolePlan(tier);
    data.role = mapped.role;
    if (mapped.plan) data.plan = mapped.plan;
  }

  if (has("plan")) {
    const plan = b.plan;
    if (!isAllowed(ALLOWED_PLANS, plan)) {
      return { ok: false, status: 400, error: `plan must be one of: ${ALLOWED_PLANS.join(", ")}` };
    }
    data.plan = plan;
  }

  if (has("role")) {
    const role = b.role;
    if (!isAllowed(ALLOWED_ROLES, role)) {
      return { ok: false, status: 400, error: `role must be one of: ${ALLOWED_ROLES.join(", ")}` };
    }
    data.role = role;
  }

  if (has("subscription_status")) {
    const status = b.subscription_status;
    if (!isAllowed(ALLOWED_STATUSES, status)) {
      return {
        ok: false,
        status: 400,
        error: `subscription_status must be one of: ${ALLOWED_STATUSES.join(", ")}`,
      };
    }
    data.subscription_status = status;
  }

  if (has("is_active")) {
    if (typeof b.is_active !== "boolean") {
      return { ok: false, status: 400, error: "is_active must be a boolean" };
    }
    data.is_active = b.is_active ? "true" : "false";
  }

  if (Object.keys(data).length === 0) {
    return { ok: false, status: 400, error: "Nothing to update" };
  }

  const isSelf = target.id === actorId;
  const demoting = isAdminRole(target.role) && data.role !== undefined && !isAdminRole(data.role);

  if (isSelf && demoting) {
    return { ok: false, status: 409, error: "You can't remove your own admin access." };
  }
  if (isSelf && data.is_active === "false") {
    return { ok: false, status: 409, error: "You can't pause your own account." };
  }
  if (demoting && adminCount <= 1) {
    return { ok: false, status: 409, error: "Can't demote the last remaining admin." };
  }

  return { ok: true, data };
}
