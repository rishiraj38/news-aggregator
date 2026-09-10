import type { Plan, Tier } from "@/lib/entitlements";

/** Shapes returned by /api/admin/*. Dates are ISO strings. */

export type DeliverySummary = {
  sent_at: string | null;
  status: string;
  kind: string;
} | null;

export type AdminMember = {
  id: string;
  email: string;
  name: string;
  role: string;
  plan: Plan;
  tier: Tier;
  subscription_status: string;
  is_active: boolean;
  created_at: string | null;
  topics: string[];
  keywords: string[];
  trial_exempt: boolean;
  last_delivery: DeliverySummary;
  sent_30d: number;
  failed_30d: number;
  /** Set while a Free member has an unanswered request for Pro. */
  pro_requested_at: string | null;
};

export type AdminTotals = {
  total: number;
  free: number;
  pro: number;
  admin: number;
  expired: number;
  paused: number;
  pro_requests: number;
};

export type DeliveryArticle = {
  id: string;
  title: string;
  url: string;
  article_type: string;
};

export type AdminDelivery = {
  id: string;
  user_id: string;
  email: string;
  name: string | null;
  kind: string;
  subject: string | null;
  status: string;
  error: string | null;
  sent_at: string | null;
  pipeline_run_id: string | null;
  articles: DeliveryArticle[];
  /** Digests referenced by the email that no longer exist in the database. */
  missing_articles: number;
};

export type RecommendationDay = {
  date: string;
  items: Array<DeliveryArticle & { rank: number; score: number }>;
};

export type DeliveryDay = { date: string; sent: number; failed: number };

export type MemberPatch = Partial<{
  tier: string;
  plan: string;
  subscription_status: string;
  role: string;
  is_active: boolean;
  decline_pro_request: boolean;
}>;
