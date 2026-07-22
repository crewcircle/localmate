import { describe, it, expect } from "vitest";
import {
  rebookStats,
  conversionRate,
  dualRankingStats,
  locationStats,
  rankDelta,
} from "@/lib/stats";
import {
  stubPractitioners,
  stubDualRankings,
  stubLocations,
} from "@/lib/stubs";

describe("rebookStats", () => {
  it("aggregates practitioner metrics from stub data", () => {
    const stats = rebookStats(stubPractitioners);
    expect(stats.practitioners).toBe(4);
    expect(stats.lapsed).toBe(86);
    expect(stats.sent).toBe(52);
    expect(stats.rebooked).toBe(19);
  });

  it("returns zeros for an empty list", () => {
    expect(rebookStats([])).toEqual({
      practitioners: 0,
      lapsed: 0,
      sent: 0,
      rebooked: 0,
    });
  });

  it("handles a single practitioner", () => {
    const stats = rebookStats([stubPractitioners[0]]);
    expect(stats).toEqual({
      practitioners: 1,
      lapsed: 24,
      sent: 15,
      rebooked: 6,
    });
  });
});

describe("conversionRate", () => {
  it("computes whole-number percentage", () => {
    expect(conversionRate(15, 6)).toBe(40);
    expect(conversionRate(10, 3)).toBe(30);
    expect(conversionRate(22, 9)).toBe(41);
  });

  it("returns 0 when no follow-ups sent", () => {
    expect(conversionRate(0, 5)).toBe(0);
  });

  it("returns 0 for negative sent", () => {
    expect(conversionRate(-1, 3)).toBe(0);
  });

  it("rounds to nearest whole number", () => {
    expect(conversionRate(3, 1)).toBe(33);
    expect(conversionRate(7, 2)).toBe(29);
  });

  it("handles 100% conversion", () => {
    expect(conversionRate(5, 5)).toBe(100);
  });
});

describe("dualRankingStats", () => {
  it("computes averages and counts from stub data", () => {
    const stats = dualRankingStats(stubDualRankings);
    // organic: (2+11+5+7+6)/5 = 6.2
    expect(stats.avgOrganic).toBe(6.2);
    // local pack: (1+6+2+4+7)/5 = 4.0
    expect(stats.avgLocalPack).toBe(4.0);
    // organic improving: dentist Bondi(+1), dental implant(+5), invisalign(+3) = 3
    expect(stats.improving).toBe(3);
    // local pack top 3: #1, #2 = 2
    expect(stats.topThreeMaps).toBe(2);
  });

  it("returns zeros for empty input", () => {
    expect(dualRankingStats([])).toEqual({
      avgOrganic: 0,
      avgLocalPack: 0,
      improving: 0,
      topThreeMaps: 0,
    });
  });

  it("rounds averages to one decimal place", () => {
    const stats = dualRankingStats([
      { keyword: "a", organicThisWeek: 1, organicDelta: 1, localPackThisWeek: 2, localPackDelta: 0 },
      { keyword: "b", organicThisWeek: 2, organicDelta: 0, localPackThisWeek: 3, localPackDelta: 1 },
      { keyword: "c", organicThisWeek: 3, organicDelta: -1, localPackThisWeek: 4, localPackDelta: -1 },
    ]);
    // organic: (1+2+3)/3 = 2.0
    expect(stats.avgOrganic).toBe(2.0);
    // local pack: (2+3+4)/3 = 3.0
    expect(stats.avgLocalPack).toBe(3.0);
    expect(stats.improving).toBe(1);
    expect(stats.topThreeMaps).toBe(2); // #2 and #3 are <= 3, #4 is not
  });
});

describe("locationStats", () => {
  it("counts total and synced locations from stub data", () => {
    const stats = locationStats(stubLocations);
    expect(stats.total).toBe(6);
    expect(stats.synced).toBe(5);
  });

  it("returns zeros for empty input", () => {
    expect(locationStats([])).toEqual({ total: 0, synced: 0 });
  });
});

describe("rankDelta", () => {
  it("classifies positive delta as up", () => {
    expect(rankDelta(1)).toEqual({ direction: "up", magnitude: 1 });
    expect(rankDelta(5)).toEqual({ direction: "up", magnitude: 5 });
  });

  it("classifies negative delta as down with positive magnitude", () => {
    expect(rankDelta(-3)).toEqual({ direction: "down", magnitude: 3 });
    expect(rankDelta(-1)).toEqual({ direction: "down", magnitude: 1 });
  });

  it("classifies zero delta as none", () => {
    expect(rankDelta(0)).toEqual({ direction: "none", magnitude: 0 });
  });
});
