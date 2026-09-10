"use client";

import { useState } from "react";
import { Activity, Mail, Users } from "lucide-react";
import { PipelineStatus } from "@/components/PipelineStatus";
import { cn } from "@/lib/utils";
import DeliveriesPanel from "./DeliveriesPanel";
import MembersPanel from "./MembersPanel";

const TABS = [
  { id: "members", label: "Members", icon: Users },
  { id: "deliveries", label: "Email log", icon: Mail },
  { id: "pipeline", label: "Pipeline", icon: Activity },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function AdminConsole({ currentAdminId }: { currentAdminId: string }) {
  const [tab, setTab] = useState<TabId>("members");

  return (
    <div className="space-y-6">
      <div role="tablist" aria-label="Admin sections" className="flex flex-wrap gap-2">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              id={`admin-tab-${t.id}`}
              role="tab"
              type="button"
              aria-selected={active}
              aria-controls={`admin-panel-${t.id}`}
              onClick={() => setTab(t.id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors cursor-pointer",
                active
                  ? "bg-accent text-surface-deep"
                  : "border border-line bg-surface-raised/80 text-ink-muted hover:text-ink hover:border-line-strong",
              )}
            >
              <Icon className="w-4 h-4" strokeWidth={2} aria-hidden />
              {t.label}
            </button>
          );
        })}
      </div>

      <section
        id={`admin-panel-${tab}`}
        role="tabpanel"
        aria-labelledby={`admin-tab-${tab}`}
        className="rounded-2xl border border-line/85 bg-surface/80 backdrop-blur-sm p-4 sm:p-6 lg:p-8"
      >
        <div hidden={tab !== "members"}>
          <MembersPanel currentAdminId={currentAdminId} />
        </div>
        {tab === "deliveries" && <DeliveriesPanel />}
        {tab === "pipeline" && <PipelineStatus />}
      </section>
    </div>
  );
}
