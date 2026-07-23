"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Clock, CheckCircle2, BarChart3 } from "lucide-react";
import ReviewCard from "@/components/ReviewCard";
import { api } from "@/lib/api";
import { stubDrafts } from "@/lib/stubs";
import type { DraftReview } from "@/lib/stubs";

export default function DashboardPage() {
  const [drafts, setDrafts] = useState<DraftReview[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<DraftReview[]>("/drafts?status=pending_approval")
      .then((data) => setDrafts(data ?? stubDrafts))
      .catch(() => setDrafts(stubDrafts))
      .finally(() => setLoading(false));
  }, []);

  const stats = [
    {
      label: "Pending",
      value: drafts.length.toString(),
      icon: Clock,
      chipClass: "bg-accent/10 text-accent",
    },
    {
      label: "Posted today",
      value: "2",
      icon: CheckCircle2,
      chipClass: "bg-chart-3/10 text-chart-3",
    },
    {
      label: "Avg SLA",
      value: "3.2h",
      icon: BarChart3,
      chipClass: "bg-muted text-chart-2",
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">
          Review Approval Queue
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI-drafted responses ready for your review
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-xl ring-1 ring-foreground/10 bg-background p-4"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-9 w-9 flex-none items-center justify-center rounded-lg ${stat.chipClass}`}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-2xl font-semibold tabular-nums text-foreground">
                    {stat.value}
                  </p>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {stat.label}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {drafts.length === 0 ? (
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-12 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-chart-3" />
          <h3 className="mt-4 text-lg font-semibold text-foreground">
            All caught up!
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Check back later for new reviews needing approval.
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            New reviews appear here automatically when customers leave feedback.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {drafts.map((draft) => (
            <ReviewCard key={draft.id} review={draft} />
          ))}
        </div>
      )}
    </div>
  );
}
