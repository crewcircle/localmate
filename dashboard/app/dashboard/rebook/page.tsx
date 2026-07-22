"use client";

import { useState } from "react";
import {
  Users,
  Clock,
  MessageSquare,
  RefreshCw,
  TrendingUp,
  Building2,
  ChevronDown,
} from "lucide-react";
import DemoBadge from "@/components/DemoBadge";
import Toggle from "@/components/Toggle";
import { stubPractitioners } from "@/lib/stubs";
import type { Practitioner, LapsedPatient } from "@/lib/stubs";
import { rebookStats, conversionRate } from "@/lib/stats";

const patientStatusBadge: Record<
  LapsedPatient["status"],
  { label: string; className: string }
> = {
  rebooked: {
    label: "Rebooked",
    className: "bg-chart-3/10 text-chart-3",
  },
  sent: { label: "Sent", className: "bg-chart-4/10 text-chart-4" },
  queued: { label: "Queued", className: "bg-muted text-chart-2" },
  opted_out: {
    label: "Opted out",
    className: "bg-muted text-muted-foreground",
  },
};

const statChipColors = [
  "bg-accent/10 text-accent",
  "bg-muted text-chart-2",
  "bg-chart-4/10 text-chart-4",
  "bg-chart-3/10 text-chart-3",
];

export default function RebookPage() {
  const [autoFollowUp, setAutoFollowUp] = useState<
    Record<string, boolean>
  >(
    Object.fromEntries(
      stubPractitioners.map((p) => [p.id, p.autoFollowUp]),
    ),
  );
  const [selectedId, setSelectedId] = useState(stubPractitioners[0].id);

  const stats = rebookStats(stubPractitioners);
  const selected = stubPractitioners.find((p) => p.id === selectedId)!;
  const selectedRate = conversionRate(selected.sent, selected.rebooked);

  const statCards = [
    {
      label: "Practitioners",
      value: stats.practitioners.toString(),
      icon: Users,
    },
    {
      label: "Lapsed patients",
      value: stats.lapsed.toString(),
      icon: Clock,
    },
    {
      label: "Follow-ups sent",
      value: stats.sent.toString(),
      icon: MessageSquare,
    },
    {
      label: "Rebooked",
      value: stats.rebooked.toString(),
      icon: RefreshCw,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Rebook</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Lapsed-patient follow-up by practitioner
          </p>
        </div>
        <div className="flex items-center gap-2">
          <DemoBadge />
          <div className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground">
            <Building2 className="h-4 w-4" />
            <span>Bondi Dental Clinic</span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-lg border border-border bg-background p-4"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-9 w-9 flex-none items-center justify-center rounded-lg ${statChipColors[i]}`}
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

      <div className="overflow-x-auto rounded-lg border border-border bg-background">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">Practitioner</th>
              <th className="px-4 py-3">Lapsed patients</th>
              <th className="px-4 py-3">Follow-ups sent</th>
              <th className="px-4 py-3">Rebooked</th>
              <th className="px-4 py-3">Auto follow-up</th>
            </tr>
          </thead>
          <tbody>
            {stubPractitioners.map((p) => {
              const rate = conversionRate(p.sent, p.rebooked);
              const isOn = autoFollowUp[p.id];
              return (
                <tr
                  key={p.id}
                  className={`border-b border-border last:border-0 hover:bg-muted ${
                    selectedId === p.id ? "bg-muted/50" : ""
                  }`}
                >
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setSelectedId(p.id)}
                      className="text-left"
                    >
                      <p className="font-medium text-foreground">{p.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {p.specialty}
                      </p>
                    </button>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{p.lapsed}</td>
                  <td className="px-4 py-3 text-muted-foreground">{p.sent}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1">
                      <TrendingUp className="h-3.5 w-3.5 text-chart-3" />
                      <span className="font-medium text-foreground">
                        {p.rebooked}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({rate}%)
                      </span>
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Toggle
                        checked={isOn}
                        onChange={(v) =>
                          setAutoFollowUp({ ...autoFollowUp, [p.id]: v })
                        }
                        aria-label={`Auto follow-up for ${p.name}`}
                      />
                      <span className="text-xs text-muted-foreground">
                        {isOn ? "Follow-ups on" : "Opted out"}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <PractitionerDetail
        practitioner={selected}
        autoFollowUp={autoFollowUp[selected.id]}
        onToggleFollowUp={(v) =>
          setAutoFollowUp({ ...autoFollowUp, [selected.id]: v })
        }
        conversionRate={selectedRate}
      />
    </div>
  );
}

function PractitionerDetail({
  practitioner,
  autoFollowUp,
  onToggleFollowUp,
  conversionRate: rate,
}: {
  practitioner: Practitioner;
  autoFollowUp: boolean;
  onToggleFollowUp: (v: boolean) => void;
  conversionRate: number;
}) {
  const detailStats = [
    {
      label: "Messages sent",
      value: practitioner.sent.toString(),
      className: "text-chart-2",
    },
    {
      label: "Rebooked",
      value: practitioner.rebooked.toString(),
      className: "text-chart-3",
    },
    {
      label: "Conversion",
      value: `${rate}%`,
      className: "text-foreground",
    },
  ];

  return (
    <div className="rounded-lg border border-border bg-background p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">
            {practitioner.name}
          </h2>
          <p className="text-sm text-muted-foreground">
            {practitioner.specialty} · {practitioner.lapsed} lapsed patients
            (&gt;6 months)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Auto follow-up</span>
          <Toggle
            checked={autoFollowUp}
            onChange={onToggleFollowUp}
            aria-label={`Auto follow-up for ${practitioner.name}`}
          />
        </div>
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        {detailStats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border border-border p-4"
          >
            <p className={`text-2xl font-bold ${stat.className}`}>
              {stat.value}
            </p>
            <p className="text-xs font-medium text-muted-foreground">
              {stat.label}
            </p>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">Patient</th>
              <th className="px-4 py-3">Last visit</th>
              <th className="px-4 py-3">Channel</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {practitioner.patients.map((patient) => {
              const badge = patientStatusBadge[patient.status];
              return (
                <tr
                  key={patient.name}
                  className="border-b border-border last:border-0"
                >
                  <td className="px-4 py-3 font-medium text-foreground">
                    {patient.name}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {patient.lastVisit}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {patient.channel}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
                    >
                      {badge.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
