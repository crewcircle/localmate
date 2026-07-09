"use client";

import { Bell, CreditCard, AlertTriangle } from "lucide-react";
import { differenceInDays, parseISO } from "date-fns";
import { getTrialState } from "@/lib/trial-state";
import DemoBadge from "./DemoBadge";

interface TrialBannerProps {
  client?: {
    trial_ends_at: string;
    trial_status: string;
    card_collected_at: string | null;
    subscription_status: string;
    trial_usage: {
      review_drafts: number;
    };
  };
}

const STUB_CLIENT = {
  trial_ends_at: "2026-07-15T00:00:00+10:00",
  trial_status: "active",
  card_collected_at: null,
  subscription_status: "trial",
  trial_usage: { review_drafts: 3 },
};

const bannerStyles: Record<string, string> = {
  active: "bg-blue-50 border-blue-200 text-blue-800",
  expiring_soon: "bg-amber-50 border-amber-200 text-amber-800",
  card_required: "bg-red-50 border-red-200 text-red-800",
  expired: "bg-gray-100 border-gray-300 text-gray-600",
};

const icons: Record<string, React.ReactNode> = {
  active: <Bell className="h-4 w-4" />,
  expiring_soon: <AlertTriangle className="h-4 w-4" />,
  card_required: <AlertTriangle className="h-4 w-4" />,
  expired: <CreditCard className="h-4 w-4" />,
};

export default function TrialBanner({ client: _client }: TrialBannerProps) {
  const client = _client ?? STUB_CLIENT;
  const state = getTrialState(client);
  const daysLeft = differenceInDays(
    parseISO(client.trial_ends_at),
    new Date()
  );

  return (
    <div
      className={`sticky top-0 z-40 border-b px-4 py-2 text-sm ${bannerStyles[state]}`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-2">
          {icons[state]}
          <span>
            {state === "active" &&
              `Trial: ${daysLeft} days remaining | ${client.trial_usage.review_drafts}/100 review drafts used`}
            {state === "expiring_soon" &&
              `Trial ends in ${daysLeft} days — add card to keep your data`}
            {state === "card_required" &&
              `Trial ends tomorrow — add card now to avoid interruption`}
            {state === "expired" &&
              "Your trial ended — upgrade to restore access"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(state === "expiring_soon" || state === "card_required") && (
            <button className="rounded bg-white px-3 py-1 text-sm font-medium shadow-sm border hover:bg-gray-50">
              {state === "card_required" ? "Add card NOW" : "Add card"}
            </button>
          )}
          {state === "expired" && (
            <button className="rounded bg-gray-800 px-3 py-1 text-sm font-medium text-white hover:bg-gray-700">
              Upgrade
            </button>
          )}
          <DemoBadge />
        </div>
      </div>
    </div>
  );
}
