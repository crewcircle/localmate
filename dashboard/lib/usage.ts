import type { UsageBar } from "@/lib/stubs";

export type UsageStatus = "ok" | "near" | "over";

/** Label used for the review-drafts quota (shared with TrialBanner). */
export const REVIEW_DRAFTS = "Review drafts";

/**
 * Rounded usage percentage, capped at 100. Returns 0 when a cap is not
 * positive so the progress bar never divides by zero.
 */
export function usagePercent(bar: UsageBar): number {
  if (bar.cap <= 0) return 0;
  return Math.min(100, Math.round((bar.used / bar.cap) * 100));
}

/**
 * Bucket a usage bar into a status. Thresholds mirror the design mockups:
 * >= 100% is over cap, >= 80% is near cap, otherwise OK.
 */
export function usageStatus(bar: UsageBar): UsageStatus {
  if (bar.cap <= 0) return "over";
  const pct = (bar.used / bar.cap) * 100;
  if (pct >= 100) return "over";
  if (pct >= 80) return "near";
  return "ok";
}

/** Remaining quota for the cycle, never negative. */
export function usageRemaining(bar: UsageBar): number {
  return Math.max(0, bar.cap - bar.used);
}

/** Case-insensitive lookup of a usage bar by label. */
export function findUsageBar(
  usage: UsageBar[],
  label: string
): UsageBar | undefined {
  return usage.find((b) => b.label.toLowerCase() === label.toLowerCase());
}

/** Convenience accessor for a bar's cap, or undefined when not found. */
export function getCap(usage: UsageBar[], label: string): number | undefined {
  return findUsageBar(usage, label)?.cap;
}

/** Presentation metadata for each usage status (badge label + Tailwind classes). */
export const STATUS_STYLES: Record<
  UsageStatus,
  { label: string; badge: string; bar: string }
> = {
  ok: { label: "OK", badge: "bg-chart-3/10 text-chart-3", bar: "bg-chart-3" },
  near: {
    label: "Near cap",
    badge: "bg-muted text-chart-2",
    bar: "bg-chart-2",
  },
  over: {
    label: "Over cap",
    badge: "bg-destructive/10 text-destructive",
    bar: "bg-destructive",
  },
};
