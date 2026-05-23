import { auth } from "@clerk/nextjs/server";
import { db } from "@/lib/db";
import { canonicalTopicSelection } from "@/lib/topics";

export async function PATCH(req: Request) {
  const { userId } = await auth();
  if (!userId) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!body || typeof body !== "object") {
    return Response.json({ error: "Invalid body" }, { status: 400 });
  }

  if (!Object.prototype.hasOwnProperty.call(body, "topics")) {
    return Response.json({ error: "Missing topics payload" }, { status: 400 });
  }

  const topics = canonicalTopicSelection(body.topics);

  const user = await db.user.findUnique({ where: { id: userId } });
  if (!user) {
    return Response.json({ error: "User not synced yet — open dashboard once" }, { status: 404 });
  }

  let prefs: Record<string, unknown> = {};
  try {
    prefs = JSON.parse(user.preferences || "{}") as Record<string, unknown>;
  } catch {
    prefs = {};
  }

  prefs.topics = topics;

  await db.user.update({
    where: { id: userId },
    data: { preferences: JSON.stringify(prefs) },
  });

  return Response.json({ ok: true, topics });
}
