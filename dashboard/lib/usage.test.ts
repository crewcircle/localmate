import { describe, it, expect } from "vitest";
import {
  usagePercent,
  usageStatus,
  usageRemaining,
  findUsageBar,
  getCap,
  STATUS_STYLES,
  REVIEW_DRAFTS,
} from "./usage";
import type { UsageBar } from "./stubs";

const bar = (used: number, cap: number): UsageBar => ({
  label: "Review drafts",
  used,
  cap,
});

describe("usagePercent", () => {
  it("computes a rounded percentage", () => {
    expect(usagePercent(bar(212, 500))).toBe(42);
    expect(usagePercent(bar(6, 8))).toBe(75);
    expect(usagePercent(bar(4, 5))).toBe(80);
  });

  it("caps at 100", () => {
    expect(usagePercent(bar(600, 500))).toBe(100);
  });

  it("returns 0 for zero or negative caps", () => {
    expect(usagePercent(bar(5, 0))).toBe(0);
    expect(usagePercent(bar(5, -1))).toBe(0);
  });
});

describe("usageStatus", () => {
  it("is ok below 80%", () => {
    expect(usageStatus(bar(0, 100))).toBe("ok");
    expect(usageStatus(bar(79, 100))).toBe("ok");
  });

  it("is near at 80% inclusive up to (but not including) 100%", () => {
    expect(usageStatus(bar(80, 100))).toBe("near");
    expect(usageStatus(bar(99, 100))).toBe("near");
  });

  it("is over at 100% and above", () => {
    expect(usageStatus(bar(100, 100))).toBe("over");
    expect(usageStatus(bar(150, 100))).toBe("over");
  });

  it("is over when the cap is zero or negative", () => {
    expect(usageStatus(bar(0, 0))).toBe("over");
    expect(usageStatus(bar(0, -5))).toBe("over");
  });
});

describe("usageRemaining", () => {
  it("returns cap - used", () => {
    expect(usageRemaining(bar(212, 500))).toBe(288);
  });

  it("never goes negative", () => {
    expect(usageRemaining(bar(600, 500))).toBe(0);
  });
});

describe("findUsageBar / getCap", () => {
  const usage: UsageBar[] = [
    { label: "Review drafts", used: 212, cap: 500 },
    { label: "SEO reports", used: 6, cap: 8 },
  ];

  it("finds a bar by label, case-insensitively", () => {
    expect(findUsageBar(usage, "review drafts")?.cap).toBe(500);
    expect(findUsageBar(usage, "SEO Reports")?.cap).toBe(8);
  });

  it("returns undefined for a missing label", () => {
    expect(findUsageBar(usage, "Nope")).toBeUndefined();
  });

  it("getCap returns the cap or undefined", () => {
    expect(getCap(usage, REVIEW_DRAFTS)).toBe(500);
    expect(getCap(usage, "Missing")).toBeUndefined();
  });
});

describe("STATUS_STYLES", () => {
  it("exposes a label for every status", () => {
    expect(STATUS_STYLES.ok.label).toBe("OK");
    expect(STATUS_STYLES.near.label).toBe("Near cap");
    expect(STATUS_STYLES.over.label).toBe("Over cap");
  });

  it("every status has non-empty badge and bar classes", () => {
    for (const key of ["ok", "near", "over"] as const) {
      expect(STATUS_STYLES[key].badge).toBeTruthy();
      expect(STATUS_STYLES[key].bar).toBeTruthy();
    }
  });
});
