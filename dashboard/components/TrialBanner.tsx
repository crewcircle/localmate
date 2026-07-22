"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, CreditCard, AlertTriangle, Check } from "lucide-react";
import { differenceInDays, parseISO } from "date-fns";
import { getTrialState } from "@/lib/trial-state";
import { api } from "@/lib/api";
import { stubBillingUsage } from "@/lib/stubs";
import type { BillingUsage, PlanInfo } from "@/lib/stubs";
import { getCap, REVIEW_DRAFTS } from "@/lib/usage";
import DemoBadge from "./DemoBadge";

interface TrialBannerProps {
  client?: {
    trial_ends_at: string;
    trial_status: string;
    card_collected_at: string | null;
    subscription_status: string;
    trial_usage: {
      review_drafts: number;
    };
  };
}

const STUB_CLIENT = {
  trial_ends_at: "2026-07-15T00:00:00+10:00",
  trial_status: "active",
  card_collected_at: null,
  subscription_status: "trial",
  trial_usage: { review_drafts: 3 },
};

/** Fallback cap for the review-drafts quota when usage data is unavailable. */
const DEFAULT_REVIEW_CAP = 100;

const bannerStyles: Record<string, string> = {
  active: "bg-accent/10 border-accent/20 text-accent",
  expiring_soon: "bg-muted border-chart-2/20 text-chart-2",
  card_required: "bg-destructive/10 border-destructive/20 text-destructive",
  expired: "bg-muted/50 border-border text-muted-foreground",
};

const icons: Record<string, React.ReactNode> = {
  active: <Bell className="h-4 w-4" />,
  expiring_soon: <AlertTriangle className="h-4 w-4" />,
  card_required: <AlertTriangle className="h-4 w-4" />,
  expired: <CreditCard className="h-4 w-4" />,
};

/** Green banner shown for active paid plans (plan name + Manage billing). */
function UsageBanner({ plan }: { plan: PlanInfo }) {
  return (
    <div className="sticky top-0 z-40 border-b border-chart-3/25 bg-chart-3/10 px-4 py-2 text-sm text-chart-3">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-2">
          <Check className="h-4 w-4" />
          <span>
            {plan.name} plan · renews {plan.renews_at}
            {plan.card && ` · ${plan.card.brand} •••• ${plan.card.last4}`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/billing"
            className="rounded border border-border bg-background px-3 py-1 text-sm font-medium text-foreground shadow-sm hover:bg-muted"
          >
            Manage billing
          </Link>
          <DemoBadge />
        </div>
      </div>
    </div>
  );
}

export default function TrialBanner({ client: _client }: TrialBannerProps) {
  const client = _client ?? STUB_CLIENT;
  // Seed with the stub so the banner renders immediately (no flash) and falls
  // back to it when the live billing endpoint is unavailable.
  const [billing, setBilling] = useState<BillingUsage>(stubBillingUsage);

  useEffect(() => {
    let mounted = true;
    api.get<BillingUsage>("/billing/usage").then((data) => {
      if (mounted && data) setBilling(data);
    });
    return () => {
      mounted = false;
    };
  }, []);

  // Active paid plan → green usage banner.
  if (billing.plan.status === "active") {
    return <UsageBanner plan={billing.plan} />;
  }

  const state = getTrialState(client);
  const daysLeft = differenceInDays(
    parseISO(client.trial_ends_at),
    new Date()
  );
  // Live review-drafts cap from the billing endpoint (replaces the old
  // hardcoded /100), falling back to the trial default.
  const reviewDraftsCap =
    getCap(billing.usage, REVIEW_DRAFTS) ?? DEFAULT_REVIEW_CAP;

  return (
    <div
      className={`sticky top-0 z-40 border-b px-4 py-2 text-sm ${bannerStyles[state]}`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-2">
          {icons[state]}
          <span>
            {state === "active" &&
              `Trial: ${daysLeft} days remaining | ${client.trial_usage.review_drafts}/${reviewDraftsCap} review drafts used`}
            {state === "expiring_soon" &&
              `Trial ends in ${daysLeft} days — add card to keep your data`}
            {state === "card_required" &&
              `Trial ends tomorrow — add card now to avoid interruption`}
            {state === "expired" &&
              "Your trial ended — upgrade to restore access"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(state === "expiring_soon" || state === "card_required") && (
            <button className="rounded bg-background px-3 py-1 text-sm font-medium shadow-sm border border-border hover:bg-muted">
              {state === "card_required" ? "Add card NOW" : "Add card"}
            </button>
          )}
          {state === "expired" && (
            <button className="rounded bg-primary px-3 py-1 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              Upgrade
            </button>
          )}
          <DemoBadge />
        </div>
      </div>
    </div>
  );
}
