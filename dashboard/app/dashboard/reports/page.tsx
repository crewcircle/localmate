"use client";

import { useState } from "react";
import {
  RefreshCw,
  Mail,
  Search,
  MapPin,
  TrendingUp,
  DollarSign,
  BookOpen,
  Clock,
  ChevronRight,
} from "lucide-react";
import DualRankingTable from "@/components/DualRankingTable";
import DemoBadge from "@/components/DemoBadge";
import { stubDualRankings, stubCompetitorChanges } from "@/lib/stubs";
import type { StructuredDiff } from "@/lib/stubs";
import { dualRankingStats } from "@/lib/stats";

const threatColors: Record<string, string> = {
  low: "bg-chart-3/10 text-chart-3",
  medium: "bg-muted text-chart-2",
  high: "bg-destructive/10 text-destructive",
};

const diffTypeMeta: Record<
  StructuredDiff["type"],
  { icon: typeof DollarSign; chipBg: string; pillBg: string }
> = {
  price: {
    icon: DollarSign,
    chipBg: "bg-destructive/10 text-destructive",
    pillBg: "bg-destructive/10 text-destructive",
  },
  menu: {
    icon: BookOpen,
    chipBg: "bg-chart-4/10 text-chart-4",
    pillBg: "bg-chart-4/10 text-chart-4",
  },
  hours: {
    icon: Clock,
    chipBg: "bg-chart-3/10 text-chart-3",
    pillBg: "bg-chart-3/10 text-chart-3",
  },
};

const legendItems: {
  type: StructuredDiff["type"];
  label: string;
  pillClass: string;
}[] = [
  { type: "price", label: "Price change", pillClass: "bg-destructive/10 text-destructive" },
  { type: "menu", label: "Menu / service change", pillClass: "bg-chart-4/10 text-chart-4" },
  { type: "hours", label: "Hours change", pillClass: "bg-chart-3/10 text-chart-3" },
];

export default function ReportsPage() {
  const [tab, setTab] = useState<"seo" | "competitors">("seo");

  const rankingStats = dualRankingStats(stubDualRankings);
  const totalChanges = stubCompetitorChanges.reduce(
    (s, c) => s + c.changes.length,
    0,
  );

  const seoStats = [
    {
      label: "Avg organic rank",
      value: rankingStats.avgOrganic.toFixed(1),
      icon: Search,
      chipClass: "bg-muted text-muted-foreground",
    },
    {
      label: "Avg Local Pack rank",
      value: rankingStats.avgLocalPack.toFixed(1),
      icon: MapPin,
      chipClass: "bg-chart-4/10 text-chart-4",
    },
    {
      label: "Keywords improving",
      value: rankingStats.improving.toString(),
      icon: TrendingUp,
      chipClass: "bg-chart-3/10 text-chart-3",
    },
    {
      label: "In top 3 (Maps)",
      value: rankingStats.topThreeMaps.toString(),
      icon: MapPin,
      chipClass: "bg-accent/10 text-accent",
    },
  ];

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
          <DemoBadge />
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
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {seoStats.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.label}
                  className="rounded-lg border border-border bg-background p-4"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`flex h-9 w-9 flex-none items-center justify-center rounded-lg ${stat.chipClass}`}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <div>
                      <p className="text-2xl font-bold text-foreground">
                        {stat.value}
                      </p>
                      <p className="text-xs font-medium text-muted-foreground">
                        {stat.label}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="rounded-lg border border-border bg-background p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                Keyword Rankings
              </h2>
              <span className="text-xs text-muted-foreground">
                Updated 21 Jul 2026, 6:00 AM
              </span>
            </div>
            <DualRankingTable data={stubDualRankings} />
          </div>
        </>
      ) : (
        <>
          <div className="rounded-lg border border-border bg-background p-4">
            <div className="flex flex-wrap items-center gap-4">
              {legendItems.map((item) => {
                const Icon = diffTypeMeta[item.type].icon;
                return (
                  <span
                    key={item.type}
                    className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span
                      className={`rounded px-1.5 py-0.5 text-xs font-medium ${item.pillClass}`}
                    >
                      {item.label}
                    </span>
                  </span>
                );
              })}
              <span className="ml-auto text-xs text-muted-foreground">
                {totalChanges} structured changes across{" "}
                {stubCompetitorChanges.length} competitors this week
              </span>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {stubCompetitorChanges.map((competitor) => (
              <div
                key={competitor.domain}
                className="overflow-hidden rounded-lg border border-border bg-background"
              >
                <div className="border-b border-border p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">
                        {competitor.name}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {competitor.domain}
                      </p>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${threatColors[competitor.threat]}`}
                    >
                      {competitor.threat.toUpperCase()}
                    </span>
                  </div>
                </div>
                <div>
                  {competitor.changes.map((change, idx) => {
                    const meta = diffTypeMeta[change.type];
                    const Icon = meta.icon;
                    return (
                      <div
                        key={idx}
                        className={`flex items-start justify-between gap-2 p-4 ${
                          idx < competitor.changes.length - 1
                            ? "border-b border-border"
                            : ""
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <span
                            className={`flex h-8 w-8 flex-none items-center justify-center rounded-lg ${meta.chipBg}`}
                          >
                            <Icon className="h-3.5 w-3.5" />
                          </span>
                          <div>
                            <p className="text-sm font-medium text-foreground">
                              {change.description}
                            </p>
                            <div className="mt-1.5 flex flex-wrap items-center gap-2">
                              <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground line-through opacity-60">
                                {change.oldValue}
                              </span>
                              <ChevronRight className="h-3 w-3 text-muted-foreground" />
                              <span
                                className={`rounded px-1.5 py-0.5 text-xs font-medium ${meta.pillBg}`}
                              >
                                {change.newValue}
                              </span>
                            </div>
                          </div>
                        </div>
                        <span className="whitespace-nowrap text-xs text-muted-foreground">
                          {change.timestamp}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
