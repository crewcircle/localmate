"use client";

import { useState } from "react";
import { RefreshCw, Mail } from "lucide-react";
import RankingChart from "@/components/RankingChart";
import DemoBadge from "@/components/DemoBadge";
import { stubRankings, stubCompetitorBriefs } from "@/lib/stubs";

const threatColors: Record<string, string> = {
  low: "bg-green-100 text-green-700",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-red-100 text-red-700",
};

export default function ReportsPage() {
  const [tab, setTab] = useState<"seo" | "competitors">("seo");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
          <p className="mt-1 text-sm text-gray-500">
            SEO rankings and competitor intelligence
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-1 rounded border px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50">
            <RefreshCw className="h-4 w-4" /> Refresh data
          </button>
          <button className="inline-flex items-center gap-1 rounded border px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-50">
            <Mail className="h-4 w-4" /> Email report
          </button>
          <DemoBadge />
        </div>
      </div>

      <div className="flex gap-4 border-b">
        <button
          onClick={() => setTab("seo")}
          className={`pb-2 text-sm font-medium ${
            tab === "seo"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          SEO Rankings
        </button>
        <button
          onClick={() => setTab("competitors")}
          className={`pb-2 text-sm font-medium ${
            tab === "competitors"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Competitor Watch
        </button>
      </div>

      {tab === "seo" ? (
        <div className="rounded-lg border bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Keyword Rankings
          </h2>
          <RankingChart data={stubRankings} />
        </div>
      ) : (
        <div className="space-y-4">
          {stubCompetitorBriefs.map((brief) => (
            <div
              key={brief.name}
              className="rounded-lg border bg-white p-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{brief.name}</h3>
                  <p className="text-sm text-gray-500">{brief.domain}</p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    threatColors[brief.threat]
                  }`}
                >
                  {brief.threat.toUpperCase()}
                </span>
              </div>
              <p className="mt-2 text-sm text-gray-700">{brief.note}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
