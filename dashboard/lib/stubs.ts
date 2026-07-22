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

// --- Phase 5: Billing & Usage ---

/** Per-job usage with used amount and plan cap. */
export interface UsageBar {
  label: string;
  used: number;
  cap: number;
}

/** Stored payment card, if one is on file. */
export interface PlanCard {
  brand: string;
  last4: string;
  expires: string;
  valid: boolean;
}

/** Active plan details returned by GET /billing/usage. */
export interface PlanInfo {
  name: string;
  status: "active" | "trial" | "trial_expired";
  price: string;
  renews_at: string;
  days_left: number;
  card: PlanCard | null;
  billing_email: string;
  next_invoice: { amount: string; date: string };
}

/** A single line in the invoice history table. */
export interface Invoice {
  id: string;
  date: string;
  amount: string;
  status: "paid" | "open" | "void";
}

/** Aggregate billing/usage payload returned by GET /billing/usage. */
export interface BillingUsage {
  plan: PlanInfo;
  usage: UsageBar[];
  invoices: Invoice[];
}

/** Stripe billing-portal session returned by POST /billing/portal. */
export interface BillingPortal {
  url: string;
}

export const stubPlanInfo: PlanInfo = {
  name: "Growth",
  status: "active",
  price: "A$149 / month",
  renews_at: "1 Aug 2026",
  days_left: 11,
  card: { brand: "Visa", last4: "4242", expires: "08 / 2027", valid: true },
  billing_email: "accounts@bondidental.com.au",
  next_invoice: { amount: "A$149.00", date: "1 Aug 2026" },
};

export const stubUsageBars: UsageBar[] = [
  { label: "Review drafts", used: 212, cap: 500 },
  { label: "SEO reports", used: 6, cap: 8 },
  { label: "Competitor briefs", used: 4, cap: 5 },
  { label: "Follow-up messages", used: 188, cap: 250 },
];

export const stubInvoices: Invoice[] = [
  { id: "inv_2026_07", date: "1 Jul 2026", amount: "A$149.00", status: "paid" },
  { id: "inv_2026_06", date: "1 Jun 2026", amount: "A$149.00", status: "paid" },
  { id: "inv_2026_05", date: "1 May 2026", amount: "A$149.00", status: "paid" },
];

export const stubBillingUsage: BillingUsage = {
  plan: stubPlanInfo,
  usage: stubUsageBars,
  invoices: stubInvoices,
};

/* ------------------------------------------------------------------ */
/* Phase 5 — Locations, Rebook, Dual-rank reports, Competitor diffs    */
/* ------------------------------------------------------------------ */

export interface MenuSyncTarget {
  key: string;
  label: string;
  subtitle: string;
  enabled: boolean;
}

export interface Location {
  id: string;
  name: string;
  area: string;
  menuSyncTarget: string;
  status: "synced" | "setup_needed";
  lastSync: string;
  targets: MenuSyncTarget[];
}

export interface LapsedPatient {
  name: string;
  lastVisit: string;
  channel: string;
  status: "rebooked" | "sent" | "queued" | "opted_out";
}

export interface Practitioner {
  id: string;
  name: string;
  specialty: string;
  lapsed: number;
  sent: number;
  rebooked: number;
  autoFollowUp: boolean;
  patients: LapsedPatient[];
}

export interface DualRanking {
  keyword: string;
  organicThisWeek: number;
  organicDelta: number;
  localPackThisWeek: number;
  localPackDelta: number;
}

export interface StructuredDiff {
  type: "price" | "menu" | "hours";
  description: string;
  oldValue: string;
  newValue: string;
  timestamp: string;
}

export interface CompetitorChange {
  name: string;
  domain: string;
  threat: "low" | "medium" | "high";
  changes: StructuredDiff[];
}

export const stubLocations: Location[] = [
  {
    id: "loc1",
    name: "Bondi Dental — Bondi Junction",
    area: "Bondi Junction, NSW",
    menuSyncTarget: "Google Business Profile + HealthEngine",
    status: "synced",
    lastSync: "5m ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "12 services mapped", enabled: true },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
  {
    id: "loc2",
    name: "Bondi Dental — Surry Hills",
    area: "Surry Hills, NSW",
    menuSyncTarget: "Google Business Profile + HealthEngine",
    status: "synced",
    lastSync: "5m ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "10 services mapped", enabled: true },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
  {
    id: "loc3",
    name: "Bondi Dental — Chatswood",
    area: "Chatswood, NSW",
    menuSyncTarget: "Google Business Profile",
    status: "synced",
    lastSync: "12m ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "Not connected", enabled: false },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
  {
    id: "loc4",
    name: "Bondi Dental — Parramatta",
    area: "Parramatta, NSW",
    menuSyncTarget: "Google Business Profile + Doctify",
    status: "synced",
    lastSync: "1h ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "Not connected", enabled: false },
      { key: "doctify", label: "Doctify", subtitle: "8 services mapped", enabled: true },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
  {
    id: "loc5",
    name: "Bondi Dental — Newtown",
    area: "Newtown, NSW",
    menuSyncTarget: "Google Business Profile",
    status: "synced",
    lastSync: "3h ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "Not connected", enabled: false },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
  {
    id: "loc6",
    name: "Bondi Dental — Manly",
    area: "Manly, NSW",
    menuSyncTarget: "Not configured",
    status: "setup_needed",
    lastSync: "—",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Not connected", enabled: false },
      { key: "healthengine", label: "HealthEngine", subtitle: "Not connected", enabled: false },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: false },
    ],
  },
];

export const stubPractitioners: Practitioner[] = [
  {
    id: "p1",
    name: "Dr Sarah Chen",
    specialty: "General dentistry",
    lapsed: 24,
    sent: 15,
    rebooked: 6,
    autoFollowUp: true,
    patients: [
      { name: "J. Adams", lastVisit: "Nov 2025", channel: "SMS", status: "rebooked" },
      { name: "T. Nguyen", lastVisit: "Oct 2025", channel: "Email", status: "sent" },
      { name: "Y. Patel", lastVisit: "Sep 2025", channel: "SMS", status: "queued" },
      { name: "R. Williams", lastVisit: "Dec 2025", channel: "—", status: "opted_out" },
    ],
  },
  {
    id: "p2",
    name: "Dr James Wilson",
    specialty: "Orthodontics",
    lapsed: 31,
    sent: 22,
    rebooked: 9,
    autoFollowUp: true,
    patients: [
      { name: "L. Garcia", lastVisit: "Oct 2025", channel: "SMS", status: "rebooked" },
      { name: "M. Thompson", lastVisit: "Aug 2025", channel: "Email", status: "sent" },
      { name: "K. O'Brien", lastVisit: "Jul 2025", channel: "SMS", status: "queued" },
    ],
  },
  {
    id: "p3",
    name: "Dr Emily Tran",
    specialty: "Hygiene",
    lapsed: 18,
    sent: 10,
    rebooked: 3,
    autoFollowUp: false,
    patients: [
      { name: "D. Kim", lastVisit: "Nov 2025", channel: "SMS", status: "rebooked" },
      { name: "S. Murphy", lastVisit: "Sep 2025", channel: "Email", status: "sent" },
    ],
  },
  {
    id: "p4",
    name: "Dr Michael Brown",
    specialty: "Implants",
    lapsed: 13,
    sent: 5,
    rebooked: 1,
    autoFollowUp: true,
    patients: [
      { name: "A. Rossi", lastVisit: "Oct 2025", channel: "Email", status: "rebooked" },
      { name: "C. Davies", lastVisit: "Aug 2025", channel: "SMS", status: "sent" },
    ],
  },
];

export const stubDualRankings: DualRanking[] = [
  { keyword: "dentist Bondi", organicThisWeek: 2, organicDelta: 1, localPackThisWeek: 1, localPackDelta: 1 },
  { keyword: "teeth whitening Sydney", organicThisWeek: 11, organicDelta: -3, localPackThisWeek: 6, localPackDelta: -1 },
  { keyword: "emergency dentist", organicThisWeek: 5, organicDelta: 0, localPackThisWeek: 2, localPackDelta: 1 },
  { keyword: "dental implant", organicThisWeek: 7, organicDelta: 5, localPackThisWeek: 4, localPackDelta: 5 },
  { keyword: "invisalign", organicThisWeek: 6, organicDelta: 3, localPackThisWeek: 7, localPackDelta: 0 },
];

export const stubCompetitorChanges: CompetitorChange[] = [
  {
    name: "Bondi Beach Dental",
    domain: "bondibeachdental.com.au",
    threat: "high",
    changes: [
      { type: "price", description: "Teeth whitening price changed", oldValue: "A$450", newValue: "A$390", timestamp: "2h ago" },
      { type: "menu", description: "Added service: Same-day emergency", oldValue: "Not offered", newValue: "Now offered", timestamp: "2h ago" },
      { type: "price", description: "Consultation fee changed", oldValue: "A$95", newValue: "A$120", timestamp: "1d ago" },
    ],
  },
  {
    name: "Sydney Smiles Dental",
    domain: "sydneysmiles.com.au",
    threat: "medium",
    changes: [
      { type: "menu", description: "Menu item added: Invisalign Lite", oldValue: "—", newValue: "A$2,900", timestamp: "6h ago" },
      { type: "hours", description: "Opening hours updated", oldValue: "Sat closed", newValue: "Sat 9–13", timestamp: "3d ago" },
    ],
  },
];
