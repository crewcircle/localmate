export interface DraftReview {
  id: string;
  review: string;
  reviewer: string;
  rating: number;
  source: string;
  draft: string;
  created_at: string;
}

export interface Ranking {
  keyword: string;
  lastWeek: number;
  thisWeek: number;
}

export interface CompetitorBrief {
  name: string;
  domain: string;
  threat: "low" | "medium" | "high";
  note: string;
}

export interface Client {
  id: string;
  business_name: string;
  business_type: string;
  suburb: string;
  state: string;
  trial_status: "active" | "expiring_soon" | "expired";
  trial_ends_at: string;
  card_collected_at: string | null;
  subscription_status: string;
  active_jobs: string[];
  trial_usage: {
    review_drafts: number;
  };
}

export interface UserClient {
  trial_ends_at: string;
  trial_status: string;
  card_collected_at: string | null;
  subscription_status: string;
  trial_usage: {
    review_drafts: number;
    rankings: number;
    competitors: number;
  };
}

export const stubDrafts: DraftReview[] = [
  {
    id: "d1",
    review:
      "Appointment was 20 minutes late but Dr Chen was thorough and gentle. Would recommend.",
    reviewer: "Sarah M",
    rating: 4,
    source: "google",
    draft:
      "Hi Sarah, thanks for the kind words about Dr Chen. Sorry again about the wait — we've adjusted our booking slots so this won't happen again. Hope to see you back soon. — Bondi Dental",
    created_at: "2026-07-01T10:30:00+10:00",
  },
  {
    id: "d2",
    review:
      "Receptionist was rude on the phone. Hung up on me when I asked about payment plans.",
    reviewer: "James K",
    rating: 1,
    source: "google",
    draft:
      "Hi James, I'm really sorry to hear about your experience. That's not the standard we aim for. Our team has been reminded about phone etiquette, and I'd like to personally help with your payment plan enquiry. Please call us and ask for the practice manager. — Bondi Dental",
    created_at: "2026-07-01T14:00:00+10:00",
  },
  {
    id: "d3",
    review:
      "Best dentist I've been to in years. Clean facility, friendly staff, pain-free procedure.",
    reviewer: "Emily T",
    rating: 5,
    source: "google",
    draft:
      "Hi Emily, that's wonderful to hear! Our team works hard to make every visit comfortable and pain-free. Thank you for taking the time to share your experience. See you at your next check-up! — Bondi Dental",
    created_at: "2026-06-30T09:15:00+10:00",
  },
];

export const stubRankings: Ranking[] = [
  { keyword: "dentist Bondi", lastWeek: 3, thisWeek: 2 },
  { keyword: "teeth whitening Sydney", lastWeek: 8, thisWeek: 11 },
  { keyword: "emergency dentist", lastWeek: 5, thisWeek: 5 },
  { keyword: "dental implant", lastWeek: 12, thisWeek: 7 },
  { keyword: "invisalign", lastWeek: 9, thisWeek: 6 },
];

export const stubCompetitorBriefs: CompetitorBrief[] = [
  {
    name: "Bondi Beach Dental",
    domain: "bondibeachdental.com.au",
    threat: "high",
    note: "Launched new website with strong local SEO. Ranking #1 for 'dentist Bondi'. Recently added same-day emergency appointments.",
  },
  {
    name: "Sydney Smiles Dental",
    domain: "sydneysmiles.com.au",
    threat: "medium",
    note: "Running Google Ads for 'teeth whitening'. Blog updated weekly. No significant change in organic rankings this month.",
  },
];

export const stubClients: Client[] = [
  {
    id: "c1",
    business_name: "Bondi Dental Clinic",
    business_type: "Dental",
    suburb: "Bondi Junction",
    state: "NSW",
    trial_status: "active",
    trial_ends_at: "2026-07-15T00:00:00+10:00",
    card_collected_at: null,
    subscription_status: "trial",
    active_jobs: ["Review Guard", "Rank Report"],
    trial_usage: { review_drafts: 3 },
  },
  {
    id: "c2",
    business_name: "Surry Hills Physio",
    business_type: "Medical",
    suburb: "Surry Hills",
    state: "NSW",
    trial_status: "expiring_soon",
    trial_ends_at: "2026-07-08T00:00:00+10:00",
    card_collected_at: null,
    subscription_status: "trial",
    active_jobs: ["Review Guard"],
    trial_usage: { review_drafts: 12 },
  },
  {
    id: "c3",
    business_name: "Parramatta Legal",
    business_type: "Legal",
    suburb: "Parramatta",
    state: "NSW",
    trial_status: "expired",
    trial_ends_at: "2026-06-20T00:00:00+10:00",
    card_collected_at: "2026-06-15T00:00:00+10:00",
    subscription_status: "trial_expired",
    active_jobs: [],
    trial_usage: { review_drafts: 45 },
  },
  {
    id: "c4",
    business_name: "Newtown Fitness Hub",
    business_type: "Fitness",
    suburb: "Newtown",
    state: "NSW",
    trial_status: "active",
    trial_ends_at: "2026-07-20T00:00:00+10:00",
    card_collected_at: "2026-06-25T00:00:00+10:00",
    subscription_status: "trial",
    active_jobs: ["Review Guard", "Rank Report", "Rebook"],
    trial_usage: { review_drafts: 7 },
  },
];

export const stubUserClient: UserClient = {
  trial_ends_at: "2026-07-15T00:00:00+10:00",
  trial_status: "active",
  card_collected_at: null,
  subscription_status: "trial",
  trial_usage: { review_drafts: 3, rankings: 45, competitors: 2 },
};
