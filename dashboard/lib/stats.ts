import type {
  Practitioner,
  DualRanking,
  Location,
} from "@/lib/stubs";

export interface RebookStats {
  practitioners: number;
  lapsed: number;
  sent: number;
  rebooked: number;
}

/**
 * Aggregate rebook metrics across all practitioners.
 */
export function rebookStats(practitioners: Practitioner[]): RebookStats {
  return practitioners.reduce<RebookStats>(
    (acc, p) => ({
      practitioners: acc.practitioners + 1,
      lapsed: acc.lapsed + p.lapsed,
      sent: acc.sent + p.sent,
      rebooked: acc.rebooked + p.rebooked,
    }),
    { practitioners: 0, lapsed: 0, sent: 0, rebooked: 0 },
  );
}

/**
 * Conversion rate as a whole-number percentage (rebooked / sent).
 * Returns 0 when no follow-ups have been sent.
 */
export function conversionRate(sent: number, rebooked: number): number {
  if (sent <= 0) return 0;
  return Math.round((rebooked / sent) * 100);
}

export interface DualRankingStats {
  avgOrganic: number;
  avgLocalPack: number;
  improving: number;
  topThreeMaps: number;
}

/**
 * Compute aggregate ranking stats from dual-rank data.
 * - avgOrganic / avgLocalPack: mean of this-week ranks (1 decimal).
 * - improving: count of keywords whose organic rank improved (delta > 0).
 * - topThreeMaps: count of keywords in Local Pack top 3 (rank <= 3).
 */
export function dualRankingStats(rankings: DualRanking[]): DualRankingStats {
  if (rankings.length === 0) {
    return { avgOrganic: 0, avgLocalPack: 0, improving: 0, topThreeMaps: 0 };
  }
  const sumOrganic = rankings.reduce((s, r) => s + r.organicThisWeek, 0);
  const sumLocalPack = rankings.reduce((s, r) => s + r.localPackThisWeek, 0);
  return {
    avgOrganic: round1(sumOrganic / rankings.length),
    avgLocalPack: round1(sumLocalPack / rankings.length),
    improving: rankings.filter((r) => r.organicDelta > 0).length,
    topThreeMaps: rankings.filter((r) => r.localPackThisWeek <= 3).length,
  };
}

export interface LocationStats {
  total: number;
  synced: number;
}

/**
 * Count total locations and how many have menu-sync configured.
 */
export function locationStats(locations: Location[]): LocationStats {
  return {
    total: locations.length,
    synced: locations.filter((l) => l.status === "synced").length,
  };
}

export type DeltaDirection = "up" | "down" | "none";

export interface RankDelta {
  direction: DeltaDirection;
  /** Absolute magnitude of the change. */
  magnitude: number;
}

/**
 * Classify a rank delta.
 * Positive delta = rank improved (moved up, lower number is better).
 */
export function rankDelta(delta: number): RankDelta {
  if (delta > 0) return { direction: "up", magnitude: delta };
  if (delta < 0) return { direction: "down", magnitude: Math.abs(delta) };
  return { direction: "none", magnitude: 0 };
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}
