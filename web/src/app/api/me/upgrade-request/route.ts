import { auth } from "@clerk/nextjs/server";
import { getCurrentDbUser } from "@/lib/admin-auth";
import { db } from "@/lib/db";
import { canRequestPro, effectiveTier } from "@/lib/entitlements";

/**
 * Request Pro access.
 *
 * There is no payment step yet. During early access a request is reviewed in
 * the admin console, where an admin approves it by setting the member's tier to
 * Pro (which also clears the request). When payments exist, a successful
 * checkout should grant Pro directly instead of creating a request.
 *
 * Idempotent: repeating a request keeps the original timestamp, so the admin
 * queue stays ordered by when someone first asked.
 */
export async function POST() {
  const { userId } = await auth();
  if (!userId) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = await getCurrentDbUser();
  if (!user) {
    return Response.json({ error: "Open your dashboard once to finish setting up your account." }, { status: 404 });
  }

  if (!canRequestPro(user.role, user.plan)) {
    return Response.json(
      { error: "Your account already has Pro.", tier: effectiveTier(user.role, user.plan) },
      { status: 409 },
    );
  }

  if (user.pro_requested_at) {
    return Response.json({ ok: true, requested_at: user.pro_requested_at.toISOString() });
  }

  const updated = await db.user.update({
    where: { id: user.id },
    data: { pro_requested_at: new Date() },
  });

  return Response.json({ ok: true, requested_at: updated.pro_requested_at?.toISOString() ?? null });
}

/** Withdraw a pending request. */
export async function DELETE() {
  const { userId } = await auth();
  if (!userId) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = await getCurrentDbUser();
  if (!user) {
    return Response.json({ error: "User not synced yet" }, { status: 404 });
  }

  if (user.pro_requested_at) {
    await db.user.update({ where: { id: user.id }, data: { pro_requested_at: null } });
  }

  return Response.json({ ok: true });
}
