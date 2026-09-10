import { auth, currentUser } from "@clerk/nextjs/server";
import type { User } from "@prisma/client";
import { db } from "@/lib/db";
import { isAdminRole } from "@/lib/entitlements";

/**
 * The signed-in subscriber's database row, or null.
 *
 * Clerk-synced rows use the Clerk user id as their primary key; rows created
 * any other way do not, so fall back to email — which is how the dashboard has
 * always matched users.
 */
export async function getCurrentDbUser(): Promise<User | null> {
  const { userId } = await auth();
  if (!userId) return null;

  const byId = await db.user.findUnique({ where: { id: userId } });
  if (byId) return byId;

  const clerkUser = await currentUser();
  const email = clerkUser?.emailAddresses?.[0]?.emailAddress;
  return email ? db.user.findUnique({ where: { email } }) : null;
}

type Gate = { ok: true; user: User } | { ok: false; response: Response };

/**
 * Server-side admin check for API routes. Every admin endpoint must call this.
 *
 * Middleware only guarantees *someone* is signed in. Rendering an admin panel
 * only for admins does not protect the endpoint behind it — that gap is exactly
 * how /api/pipeline/status exposed every subscriber's email to any free account.
 */
export async function requireAdmin(): Promise<Gate> {
  const user = await getCurrentDbUser();
  if (!user) {
    return { ok: false, response: Response.json({ error: "Unauthorized" }, { status: 401 }) };
  }
  if (!isAdminRole(user.role)) {
    return { ok: false, response: Response.json({ error: "Forbidden" }, { status: 403 }) };
  }
  return { ok: true, user };
}
