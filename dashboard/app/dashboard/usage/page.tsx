"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Gauge,
  ShieldCheck,
  FileText,
  Search,
  MessageSquare,
  TrendingUp,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { api } from "@/lib/api";
import { stubBillingUsage } from "@/lib/stubs";
import type { BillingUsage, UsageBar } from "@/lib/stubs";
import {
  usagePercent,
  usageStatus,
  usageRemaining,
  STATUS_STYLES,
} from "@/lib/usage";

/** Per-job icon shown next to each usage bar. */
const JOB_ICONS: Record<string, LucideIcon> = {
  "Review drafts": ShieldCheck,
  "SEO reports": FileText,
  "Competitor briefs": Search,
  "Follow-up messages": MessageSquare,
};

export default function UsagePage() {
  const [billing, setBilling] = useState<BillingUsage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<BillingUsage>("/billing/usage")
      .then((data) => setBilling(data ?? stubBillingUsage))
      .catch(() => setBilling(stubBillingUsage))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !billing) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  const { plan, usage } = billing;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Usage &amp; caps</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track how much of each automation you&rsquo;ve used this cycle
          </p>
        </div>
        <Link
          href="/dashboard/billing"
          className="inline-flex items-center gap-1 rounded border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted"
        >
          Manage billing
        </Link>
      </div>

      {/* Plan card */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-background p-4">
        <div className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-[0.9375rem] font-semibold text-foreground">
              {plan.name} plan
            </p>
            <p className="text-xs text-muted-foreground">
              Billing cycle resets {plan.renews_at} &middot; {plan.days_left}{" "}
              days left
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-chart-3/10 px-2 py-0.5 text-xs font-medium text-chart-3">
          Active
        </span>
      </div>

      {/* This cycle */}
      <div className="rounded-lg border border-border bg-background">
        <div className="border-b border-border p-4">
          <h2 className="text-lg font-semibold text-foreground">This cycle</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Used / cap / remaining per job
          </p>
        </div>
        <div className="divide-y divide-border">
          {usage.map((bar) => (
            <UsageRow key={bar.label} bar={bar} />
          ))}
        </div>
      </div>

      {/* Need higher caps */}
      <div className="rounded-lg border border-border bg-background p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">
              Need higher caps?
            </span>
          </div>
          <Link
            href="/dashboard/billing"
            className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
          >
            Compare plans <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}

function UsageRow({ bar }: { bar: UsageBar }) {
  const status = usageStatus(bar);
  const pct = usagePercent(bar);
  const remaining = usageRemaining(bar);
  const styles = STATUS_STYLES[status];
  const Icon = JOB_ICONS[bar.label];

  return (
    <div className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
          <span className="text-sm font-medium text-foreground">
            {bar.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${styles.badge}`}
          >
            {styles.label}
          </span>
          <span className="font-mono text-sm">
            <strong className="font-semibold text-foreground">{bar.used}</strong>
            <span className="text-muted-foreground">/{bar.cap}</span>
          </span>
        </div>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-input">
        <div
          className={`h-full rounded-full ${styles.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        {remaining} of quota remaining this cycle
      </p>
    </div>
  );
}
