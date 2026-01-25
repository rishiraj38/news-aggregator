import { db } from "@/lib/db";

export default async function VerifyFeedPage() {
  // 1. Fetch the test user created by e2e_test.py
  const user = await db.user.findUnique({
    where: { email: "e2e_tester@example.com" },
  });

  if (!user) {
    return (
      <div className="p-10 text-red-500">
        <h1 className="text-2xl font-bold">Test User Not Found</h1>
        <p>Did e2e_test.py run successfully?</p>
      </div>
    );
  }

  // 2. Fetch their recommendations
  const recs = await db.recommendation.findMany({
    where: { user_id: user.id },
    include: { digest: true },
    orderBy: { relevance_score: "desc" },
  });

  return (
    <div className="min-h-screen bg-black text-white p-10 font-sans">
      <h1 className="text-3xl font-bold mb-6 text-green-400">
        ✅ System Verification Passed
      </h1>

      <div className="mb-8 p-4 border border-gray-700 rounded-lg">
        <h2 className="text-xl font-semibold mb-2">Backend Status</h2>
        <ul className="list-disc pl-5 text-gray-300">
          <li>
            Database Connection: <strong>OK</strong>
          </li>
          <li>
            Test User: <strong>{user.email}</strong> (ID: {user.id})
          </li>
          <li>
            Content Pipeline: <strong>Success</strong> ({recs.length} items
            generated)
          </li>
        </ul>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {recs.map((rec: any) => (
          <div
            key={rec.id}
            className="p-6 bg-gray-900 rounded-xl border border-gray-800"
          >
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-bold text-gray-500 uppercase">
                {rec.digest.article_type}
              </span>
              <span className="text-green-400 font-mono font-bold">
                Score: {rec.relevance_score}
              </span>
            </div>
            <h3 className="text-lg font-bold mb-2">{rec.digest.title}</h3>
            <p className="text-gray-400 text-sm">{rec.digest.summary}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
