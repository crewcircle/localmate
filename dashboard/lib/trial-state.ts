import { differenceInDays, parseISO } from "date-fns";

export type TrialState = "active" | "expiring_soon" | "card_required" | "expired";

export interface TrialClient {
  trial_ends_at: string;
  trial_status: string;
  card_collected_at: string | null;
  subscription_status: string;
}

export function getTrialState(client: TrialClient): TrialState {
  if (
    client.subscription_status === "trial_expired" ||
    client.trial_status === "expired"
  ) {
    return "expired";
  }
  const daysLeft = differenceInDays(
    parseISO(client.trial_ends_at),
    new Date()
  );
  if (!client.card_collected_at && daysLeft <= 2) return "card_required";
  if (daysLeft <= 5) return "expiring_soon";
  return "active";
}
