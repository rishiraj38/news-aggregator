import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import Navbar from "@/components/Navbar";
import AdminConsole from "@/components/admin/AdminConsole";
import { getCurrentDbUser } from "@/lib/admin-auth";
import { isAdminRole } from "@/lib/entitlements";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Admin console · Helix",
  robots: { index: false, follow: false },
};

export default async function AdminPage() {
  // Checked on the server: the page never renders for non-admins, and every
  // /api/admin endpoint it calls re-checks independently.
  const user = await getCurrentDbUser();
  if (!user) redirect("/sign-in");
  if (!isAdminRole(user.role)) redirect("/dashboard");

  return (
    <div className="relative z-10 min-h-dvh bg-surface-deep text-ink overflow-x-hidden">
      <Navbar isAdmin />
      <main className="relative max-w-[78rem] mx-auto px-4 sm:px-6 lg:px-10 pt-[calc(5rem+env(safe-area-inset-top))] pb-16 sm:pb-28 space-y-8">
        <header className="space-y-3">
          <p className="text-[0.7rem] uppercase tracking-[0.28em] text-ink-faint font-semibold flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-accent" strokeWidth={2} aria-hidden />
            Administrator
          </p>
          <h1 className="font-display text-[clamp(2rem,4.6vw,3.05rem)] tracking-[-0.03em] leading-[1.05]">
            Admin console
          </h1>
          <p className="text-[0.9625rem] text-ink-muted leading-relaxed max-w-[40rem]">
            Every member and their plan, who was emailed each day and exactly what was in it, and the state of the
            last pipeline run.
          </p>
        </header>
        <AdminConsole currentAdminId={user.id} />
      </main>
    </div>
  );
}
