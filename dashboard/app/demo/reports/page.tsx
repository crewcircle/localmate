// Demo route — server component using stubs only, no auth, no API calls
"use client";

import { useState } from "react";
import { RefreshCw, Mail } from "lucide-react";
import RankingChart from "@/components/RankingChart";
import { stubRankings, stubCompetitorBriefs } from "@/lib/stubs";

const threatColors: Record<string, string> = {
  low: "bg-chart-3/10 text-chart-3",
  medium: "bg-muted text-chart-2",
  high: "bg-destructive/10 text-destructive",
};

export default function DemoReportsPage() {
  const [tab, setTab] = useState<"seo" | "competitors">("seo");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Reports</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            SEO rankings and competitor intelligence
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-1 rounded border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted">
            <RefreshCw className="h-4 w-4" /> Refresh data
          </button>
          <button className="inline-flex items-center gap-1 rounded border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted">
            <Mail className="h-4 w-4" /> Email report
          </button>
        </div>
      </div>

      <div className="flex gap-4 border-b border-border">
        <button
          onClick={() => setTab("seo")}
          className={`pb-2 text-sm font-medium ${
            tab === "seo"
              ? "border-b-2 border-accent text-accent"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          SEO Rankings
        </button>
        <button
          onClick={() => setTab("competitors")}
          className={`pb-2 text-sm font-medium ${
            tab === "competitors"
              ? "border-b-2 border-accent text-accent"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Competitor Watch
        </button>
      </div>

      {tab === "seo" ? (
        <div className="rounded-lg border border-border bg-background p-6">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            Keyword Rankings
          </h2>
          <RankingChart data={stubRankings} />
        </div>
      ) : (
        <div className="space-y-4">
          {stubCompetitorBriefs.map((brief) => (
            <div
              key={brief.name}
              className="rounded-lg border border-border bg-background p-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-foreground">
                    {brief.name}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {brief.domain}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    threatColors[brief.threat]
                  }`}
                >
                  {brief.threat.toUpperCase()}
                </span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {brief.note}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
