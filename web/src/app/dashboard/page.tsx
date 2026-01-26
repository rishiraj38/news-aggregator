import { currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import Navbar from "@/components/Navbar";
import {
  Newspaper,
  Sparkles,
  Clock,
  ExternalLink,
  Lock,
  ChevronDown,
} from "lucide-react";
import { PipelineStatus } from "@/components/PipelineStatus";

export default async function Dashboard() {
  const user = await currentUser();

  if (!user) {
    redirect("/sign-in");
  }

  // 1. Sync User to Postgres (Upsert logic could be better, but check-then-create is fine for mvp)
  let dbUser: any = await db.user.findUnique({
    where: { email: user.emailAddresses[0].emailAddress },
  });

  if (!dbUser) {
    // New User! Create them in our DB so the Python Agent can find them.
    const email = user.emailAddresses[0].emailAddress;
    const name = `${user.firstName} ${user.lastName}`.trim() || "Anonymous";

    // Default Preferences
    const defaultPrefs = JSON.stringify({
      interests: ["LLMs", "Generative AI", "Tech News"],
      config: { prefer_technical_depth: true },
    });

    try {
      dbUser = await db.user.create({
        data: {
          id: user.id, // Use Clerk ID as PK
          email: email,
          name: name,
          preferences: defaultPrefs,
          is_active: "true",
          title: "New User",
          expertise_level: "Intermediate",
          role: "user",
          subscription_status: "trial",
        },
      });
      console.log("Created new user in Postgres:", dbUser.id);

      // TRIGGER WELCOME EMAIL
      try {
        const { sendWelcomeEmail } = await import("@/lib/mailer");
        await sendWelcomeEmail(email, name);
      } catch (emailErr) {
        console.error("Failed to send welcome email:", emailErr);
      }
    } catch (e) {
      console.error("Error syncing user:", e);
      // Fallback: Try to find by ID just in case email was changed or race condition
    }
  }

  // 2. Fetch Feed
  // We need to join Recommendations -> Digests
  // Prisma relation might not be set up if foreign keys aren't perfect in DB pull.
  // We'll try raw query or explicit relation if scheme supports it.
  // Since we did db pull, let's assume relations exist or we manually join.

  // Actually, 'recommendations' table has 'digest_id'. 'digests' table has 'id'.
  // We can try to fetch recommendations and then fetch digests.

  // Let's use the Prisma Client to get recommendations for this user.
  // Note: dbUser.id might differ if we found an old user by email who has a UUID.
  // Ideally we should use the dbUser.id we found.

  const recommendations = await db.recommendation.findMany({
    where: { user_id: dbUser?.id || user.id },
    orderBy: { created_at: "desc" },
    take: 20,
    include: {
      digest: true, // This requires the relation to be defined in schema.prisma
    },
  });

  return (
    <div className="min-h-screen bg-neutral-950 text-white selection:bg-purple-500/30">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-12">
        <header className="mb-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold mb-2">My Intelligence Feed</h1>
              <p className="text-gray-400">
                Welcome back,{" "}
                <span className="text-white font-medium">{user.firstName}</span>
                . Here is what the agent curated for you today.
              </p>
            </div>
            {/* User Badge */}
            <div
              className={`inline-flex items-center px-3 py-1 rounded-full border text-sm font-medium ${
                dbUser?.role === "admin"
                  ? "bg-purple-600/20 border-purple-500/40 text-purple-200"
                  : "bg-purple-500/10 border-purple-500/20 text-purple-300"
              }`}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {dbUser?.role === "admin" ? "Admin Plan" : "Free Plan"}
            </div>
          </div>
        </header>

        {/* System Status (Admin Only) */}
        {dbUser?.role === "admin" && (
          <div className="mb-8">
            <PipelineStatus />
          </div>
        )}

        {/* Locked Settings UI */}
        <section className="mb-12 bg-[#161616] border border-white/5 rounded-xl p-6 relative overflow-hidden group">
          <div className="absolute inset-0 bg-linear-to-r from-purple-900/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

          <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 flex items-center">
                Active Interest Filters{" "}
                {dbUser?.role === "admin" ? (
                  <span className="ml-2 text-xs bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded border border-purple-500/30">
                    Admin Unlocked
                  </span>
                ) : (
                  <Lock className="w-3 h-3 ml-2 text-gray-600" />
                )}
              </h3>
              <div className="flex flex-wrap gap-2">
                {(() => {
                  try {
                    // Safe parse preferences
                    const prefs = dbUser?.preferences
                      ? JSON.parse(dbUser.preferences as string)
                      : {};
                    const interests = prefs.interests || ["Tech News"];
                    return interests.map((tag: string) => (
                      <span
                        key={tag}
                        className="px-3 py-1 rounded-md bg-neutral-800 text-gray-300 text-sm border border-white/5"
                      >
                        {tag}
                      </span>
                    ));
                  } catch (e) {
                    return (
                      <span className="text-gray-500 text-sm">
                        Default Settings
                      </span>
                    );
                  }
                })()}
                <span
                  className="px-3 py-1 rounded-md border border-dashed border-gray-700 text-gray-500 text-sm flex items-center cursor-help"
                  title="Upgrade to add more"
                >
                  + Add Keyword
                </span>
              </div>
            </div>

            <div className="md:text-right">
              {dbUser?.role === "admin" ? (
                <button className="px-4 py-2 bg-purple-600 text-white font-semibold rounded-lg hover:bg-purple-500 transition text-sm flex items-center shadow-lg shadow-purple-900/20">
                  <Sparkles className="w-4 h-4 mr-2" />
                  Manage Keywords
                </button>
              ) : (
                <>
                  <button className="px-4 py-2 bg-white text-black font-semibold rounded-lg hover:bg-gray-200 transition text-sm flex items-center">
                    <Sparkles className="w-4 h-4 mr-2" />
                    Upgrade to Customize
                  </button>
                  <p className="text-xs text-gray-500 mt-2">
                    get unlimited custom keywords
                  </p>
                </>
              )}
            </div>
          </div>
        </section>

        {recommendations.length === 0 ? (
          <div className="p-12 text-center border border-white/10 rounded-2xl bg-white/5 backdrop-blur-sm">
            <Sparkles className="w-12 h-12 mx-auto mb-4 text-purple-400" />
            <h3 className="text-xl font-semibold mb-2">
              Agent Active & Learning
            </h3>
            <p className="text-gray-400 max-w-md mx-auto mb-6">
              We have registered your profile. The automated pipeline runs daily
              at midnight. Check back tomorrow for your first curated digest!
            </p>
            <div className="inline-flex items-center px-4 py-2 rounded-full bg-purple-500/10 text-purple-300 text-sm border border-purple-500/20">
              <Clock className="w-4 h-4 mr-2" />
              Next run: ~12 hours
            </div>
          </div>
        ) : (
          <GroupedFeed recommendations={recommendations} />
        )}
      </main>
    </div>
  );
}

// -- Components --

function GroupedFeed({ recommendations }: { recommendations: any[] }) {
  // Helper to group by date
  const groups = {
    today: [] as any[],
    yesterday: [] as any[],
    earlier: [] as any[],
  };

  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);

  recommendations.forEach((rec) => {
    const date = new Date(rec.digest.created_at || rec.created_at);
    if (date.toDateString() === today.toDateString()) {
      groups.today.push(rec);
    } else if (date.toDateString() === yesterday.toDateString()) {
      groups.yesterday.push(rec);
    } else {
      groups.earlier.push(rec);
    }
  });

  return (
    <div className="space-y-8">
      {groups.today.length > 0 && (
        <FeedSection
          title="Today's Digest"
          items={groups.today}
          defaultOpen={true}
        />
      )}

      {groups.yesterday.length > 0 && (
        <FeedSection
          title="Yesterday"
          items={groups.yesterday}
          defaultOpen={false}
        />
      )}

      {groups.earlier.length > 0 && (
        <FeedSection
          title="Previous Archives"
          items={groups.earlier}
          defaultOpen={false}
        />
      )}
    </div>
  );
}

function FeedSection({
  title,
  items,
  defaultOpen,
}: {
  title: string;
  items: any[];
  defaultOpen: boolean;
}) {
  return (
    <details className="group" open={defaultOpen}>
      <summary className="flex items-center cursor-pointer mb-6 list-none">
        <div className="mr-4 p-1 rounded hover:bg-white/10 transition">
          <ChevronDown className="w-5 h-5 text-gray-400 group-open:rotate-180 transition-transform" />
        </div>
        <h2 className="text-xl font-bold text-gray-200">{title}</h2>
        <div className="ml-4 h-px bg-white/10 grow" />
        <span className="ml-4 text-sm text-gray-500">
          {items.length} articles
        </span>
      </summary>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 animate-in fade-in slide-in-from-top-4 duration-500">
        {items.map((rec: any) => (
          <article
            key={rec.id}
            className="group/card relative flex flex-col justify-between p-6 bg-[#161616] border border-white/5 rounded-2xl transition hover:border-purple-500/30 hover:shadow-2xl hover:shadow-purple-900/10"
          >
            <div>
              <div className="flex justify-between items-start mb-4">
                <span className="inline-flex items-center px-2 py-1 rounded bg-white/5 text-xs text-gray-400 uppercase tracking-wider font-medium">
                  {rec.digest.article_type}
                </span>
                <span
                  className={`text-sm font-mono font-bold ${Number(rec.relevance_score) >= 8 ? "text-green-400" : "text-purple-400"}`}
                >
                  {Number(rec.relevance_score).toFixed(1)}/10
                </span>
              </div>

              <h3 className="text-lg font-bold mb-3 leading-snug group-hover/card:text-purple-300 transition-colors">
                <a
                  href={rec.digest.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="before:absolute before:inset-0"
                >
                  {rec.digest.title}
                </a>
              </h3>

              <p className="text-gray-400 text-sm line-clamp-3 mb-4">
                {rec.digest.summary}
              </p>

              <div className="bg-black/40 rounded-lg p-3 mb-4">
                <p className="text-xs text-gray-500 italic">
                  " {rec.reasoning} "
                </p>
              </div>
            </div>

            <div className="flex items-center text-xs text-gray-500 font-medium pt-4 border-t border-white/5 mt-auto">
              <Clock className="w-3 h-3 mr-1" />
              {new Date(rec.digest.created_at).toLocaleDateString()}
              <ExternalLink className="w-3 h-3 ml-auto opacity-0 group-hover/card:opacity-100 transition-opacity" />
            </div>
          </article>
        ))}
      </div>
    </details>
  );
}
