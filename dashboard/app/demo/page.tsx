// Demo route — server component using stubs only, no auth, no API calls
import { Clock, CheckCircle2, BarChart3 } from "lucide-react";
import ReviewCard from "@/components/ReviewCard";
import { stubDrafts } from "@/lib/stubs";

export default function DemoDashboardPage() {
  const stats = [
    {
      label: "Pending reviews",
      value: stubDrafts.length.toString(),
      icon: Clock,
      color: "text-accent bg-accent/10",
    },
    {
      label: "Keywords tracked",
      value: "5",
      icon: BarChart3,
      color: "text-chart-2 bg-muted",
    },
    {
      label: "Competitor briefs",
      value: "2",
      icon: CheckCircle2,
      color: "text-chart-3 bg-chart-3/10",
    },
  ];

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
            <div
              key={stat.label}
              className={`rounded-lg border border-border p-4 ${stat.color}`}
            >
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

      <div className="space-y-3">
        {stubDrafts.map((draft) => (
          <ReviewCard key={draft.id} review={draft} />
        ))}
      </div>
    </div>
  );
}
