"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Building2,
  Store,
  Star,
  MapPin,
  Plus,
  Check,
  ChevronDown,
  Calendar,
  Stethoscope,
  Globe,
} from "lucide-react";
import Toggle from "@/components/Toggle";
import { stubLocations } from "@/lib/stubs";
import type { Location } from "@/lib/stubs";
import { locationStats } from "@/lib/stats";

const targetIcons: Record<string, typeof Building2> = {
  gbp: Building2,
  healthengine: Calendar,
  doctify: Stethoscope,
  website: Globe,
};

const statusBadge: Record<Location["status"], string> = {
  synced: "bg-chart-3/10 text-chart-3",
  setup_needed: "bg-muted text-chart-2",
};

const statusLabel: Record<Location["status"], string> = {
  synced: "Synced",
  setup_needed: "Setup needed",
};

function venueName(loc: Location): string {
  const parts = loc.name.split(" — ");
  return parts.length > 1 ? parts[1] : loc.name;
}

export default function LocationsPage() {
  const [selectedId, setSelectedId] = useState(stubLocations[0].id);
  const [targets, setTargets] = useState<Record<string, boolean>>(
    Object.fromEntries(
      stubLocations[0].targets.map((t) => [t.key, t.enabled]),
    ),
  );

  const selected = stubLocations.find((l) => l.id === selectedId)!;
  const stats = locationStats(stubLocations);

  const handleSelect = (id: string) => {
    const loc = stubLocations.find((l) => l.id === id)!;
    setSelectedId(id);
    setTargets(
      Object.fromEntries(loc.targets.map((t) => [t.key, t.enabled])),
    );
  };

  const statCards = [
    {
      label: "Locations",
      value: stats.total.toString(),
      icon: Building2,
      chipClass: "bg-accent/10 text-accent",
    },
    {
      label: "Menus synced",
      value: `${stats.synced}/${stats.total}`,
      icon: Store,
      chipClass: "bg-chart-3/10 text-chart-3",
    },
    {
      label: "Reviews this week",
      value: "23",
      icon: Star,
      chipClass: "bg-muted text-chart-2",
    },
    {
      label: "Avg local rank",
      value: "4.2",
      icon: MapPin,
      chipClass: "bg-chart-4/10 text-chart-4",
    },
  ];

  const columns = [selected.targets.slice(0, 2), selected.targets.slice(2, 4)];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Locations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage venues and per-location menu-sync targets
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground">
            <Building2 className="h-4 w-4" />
            <span>Bondi Dental</span>
            <span className="text-xs text-muted-foreground">
              · {stats.total} venues
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <button
            onClick={() => toast.info("Add location coming soon")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/90 transition-colors"
          >
            <Plus className="h-4 w-4" /> Add location
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => {
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

      {/* Locations table */}
      <div className="overflow-x-auto rounded-xl ring-1 ring-foreground/10 bg-background">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3">Location</th>
              <th className="px-4 py-3">Menu-sync target</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Last sync</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {stubLocations.map((loc) => (
              <tr
                key={loc.id}
                className="border-b border-border last:border-0 hover:bg-muted"
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-foreground">{loc.name}</p>
                  <p className="text-xs text-muted-foreground">{loc.area}</p>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {loc.menuSyncTarget === "Not configured" ? (
                    <span className="italic">Not configured</span>
                  ) : (
                    loc.menuSyncTarget
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[loc.status]}`}
                  >
                    {statusLabel[loc.status]}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {loc.lastSync}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleSelect(loc.id)}
                    className="text-xs font-medium text-accent hover:text-accent/80"
                  >
                    {loc.status === "setup_needed" ? "Configure" : "Edit sync"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Menu-sync targets for selected location */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            Menu-sync targets — {venueName(selected)}
          </h2>
          {selected.status === "synced" && (
            <span className="rounded-full bg-chart-3/10 px-2 py-0.5 text-xs font-medium text-chart-3">
              Synced {selected.lastSync}
            </span>
          )}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {columns.map((col, colIdx) => (
            <div
              key={colIdx}
              className="rounded-lg ring-1 ring-foreground/10"
            >
              {col.map((target, idx) => {
                const Icon = targetIcons[target.key] ?? Store;
                return (
                  <div
                    key={target.key}
                    className={`flex items-center justify-between p-4 ${
                      idx < col.length - 1
                        ? "border-b border-border"
                        : ""
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {target.label}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {target.subtitle}
                        </p>
                      </div>
                    </div>
                    <Toggle
                      checked={targets[target.key] ?? false}
                      onChange={(v) =>
                        setTargets({ ...targets, [target.key]: v })
                      }
                      aria-label={`Toggle ${target.label}`}
                    />
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="mt-4">
          <button
            onClick={() => toast.info("Sync targets saved (demo mode)")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/90 transition-colors"
          >
            <Check className="h-4 w-4" /> Save sync targets
          </button>
        </div>
      </div>
    </div>
  );
}
