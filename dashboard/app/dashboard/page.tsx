"use client";

import { useState, useEffect } from "react";
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
      color: "text-accent bg-accent/10",
    },
    {
      label: "Posted today",
      value: "2",
      icon: CheckCircle2,
      color: "text-chart-3 bg-chart-3/10",
    },
    {
      label: "Avg SLA",
      value: "3.2h",
      icon: BarChart3,
      color: "text-chart-2 bg-muted",
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
        <h1 className="text-2xl font-bold text-foreground">
          Review Approval Queue
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI-drafted responses ready for your review
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className={`rounded-lg border border-border p-4 ${stat.color}`}>
              <div className="flex items-center gap-3">
                <Icon className="h-5 w-5" />
                <div>
                  <p className="text-2xl font-bold">{stat.value}</p>
                  <p className="text-xs font-medium">{stat.label}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {drafts.length === 0 ? (
        <div className="rounded-lg border border-border bg-background p-12 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-chart-3" />
          <h3 className="mt-4 text-lg font-semibold text-foreground">
            All caught up!
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Check back later for new reviews needing approval.
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
