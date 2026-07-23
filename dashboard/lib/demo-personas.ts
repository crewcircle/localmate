import type {
  BillingUsage,
  DraftReview,
  DualRanking,
  CompetitorChange,
  Location,
  Practitioner,
  Client,
} from "@/lib/stubs";

/* ------------------------------------------------------------------ */
/* Five personas covering every plan tier, vertical, and job mix.      */
/* ------------------------------------------------------------------ */

export type PersonaId =
  | "sarah-chen"
  | "marco-rossi"
  | "james-mitchell"
  | "emma-lewis"
  | "tom-nguyen";

export interface Persona {
  id: PersonaId;
  name: string;
  businessName: string;
  vertical: string;
  suburb: string;
  state: string;
  plan: string;
  planStatus: "active" | "trial" | "trial_expired";
  trialEndsAt: string;
  cardCollectedAt: string | null;
  jobs: string[];
  billing: BillingUsage;
  drafts: DraftReview[];
  rankings: DualRanking[];
  competitorChanges: CompetitorChange[];
  locations: Location[];
  practitioners: Practitioner[];
  client: Client;
}

/* ------------------------------------------------------------------ */
/* 1. Dr Sarah Chen — Bondi Dental Clinic (Growth, $149/mo)            */
/* ------------------------------------------------------------------ */

const sarahDrafts: DraftReview[] = [
  {
    id: "d1",
    review:
      "Appointment was 20 minutes late but Dr Chen was thorough and gentle. Would recommend.",
    reviewer: "Sarah M",
    rating: 4,
    source: "google",
    draft:
      "Hi Sarah, thanks for the kind words about Dr Chen. Sorry again about the wait — we've adjusted our booking slots so this won't happen again. Hope to see you back soon. — Bondi Dental",
    created_at: "2026-07-21T10:30:00+10:00",
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
    created_at: "2026-07-21T14:00:00+10:00",
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
    created_at: "2026-07-20T09:15:00+10:00",
  },
];

const sarahRankings: DualRanking[] = [
  { keyword: "dentist Bondi", organicThisWeek: 2, organicDelta: 1, localPackThisWeek: 1, localPackDelta: 1 },
  { keyword: "teeth whitening Sydney", organicThisWeek: 11, organicDelta: -3, localPackThisWeek: 6, localPackDelta: -1 },
  { keyword: "emergency dentist", organicThisWeek: 5, organicDelta: 0, localPackThisWeek: 2, localPackDelta: 1 },
  { keyword: "dental implant", organicThisWeek: 7, organicDelta: 5, localPackThisWeek: 4, localPackDelta: 5 },
  { keyword: "invisalign", organicThisWeek: 6, organicDelta: 3, localPackThisWeek: 7, localPackDelta: 0 },
];

const sarahCompetitorChanges: CompetitorChange[] = [
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

const sarahLocations: Location[] = [
  {
    id: "loc1", name: "Bondi Dental — Bondi Junction", area: "Bondi Junction, NSW",
    menuSyncTarget: "Google Business Profile + HealthEngine", status: "synced", lastSync: "5m ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "12 services mapped", enabled: true },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
  {
    id: "loc2", name: "Bondi Dental — Surry Hills", area: "Surry Hills, NSW",
    menuSyncTarget: "Google Business Profile + HealthEngine", status: "synced", lastSync: "5m ago",
    targets: [
      { key: "gbp", label: "Google Business Profile", subtitle: "Services & hours", enabled: true },
      { key: "healthengine", label: "HealthEngine", subtitle: "10 services mapped", enabled: true },
      { key: "doctify", label: "Doctify", subtitle: "Not connected", enabled: false },
      { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
    ],
  },
];

const sarahPractitioners: Practitioner[] = [
  {
    id: "p1", name: "Dr Sarah Chen", specialty: "General dentistry",
    lapsed: 24, sent: 15, rebooked: 6, autoFollowUp: true,
    patients: [
      { name: "J. Adams", lastVisit: "Nov 2025", channel: "SMS", status: "rebooked" },
      { name: "T. Nguyen", lastVisit: "Oct 2025", channel: "Email", status: "sent" },
      { name: "Y. Patel", lastVisit: "Sep 2025", channel: "SMS", status: "queued" },
      { name: "R. Williams", lastVisit: "Dec 2025", channel: "—", status: "opted_out" },
    ],
  },
  {
    id: "p2", name: "Dr James Wilson", specialty: "Orthodontics",
    lapsed: 31, sent: 22, rebooked: 9, autoFollowUp: true,
    patients: [
      { name: "L. Garcia", lastVisit: "Oct 2025", channel: "SMS", status: "rebooked" },
      { name: "M. Thompson", lastVisit: "Aug 2025", channel: "Email", status: "sent" },
    ],
  },
];

const sarahClient: Client = {
  id: "c-sarah",
  business_name: "Bondi Dental Clinic",
  business_type: "Dental",
  suburb: "Bondi Junction",
  state: "NSW",
  trial_status: "active",
  trial_ends_at: "2026-07-15T00:00:00+10:00",
  card_collected_at: null,
  subscription_status: "trial",
  active_jobs: ["Review Guard", "Rebook", "Rank Report"],
  trial_usage: { review_drafts: 3 },
};

const sarahBilling: BillingUsage = {
  plan: {
    name: "Growth",
    status: "active",
    price: "A$149 / month",
    renews_at: "1 Aug 2026",
    days_left: 9,
    card: { brand: "Visa", last4: "4242", expires: "08 / 2027", valid: true },
    billing_email: "accounts@bondidental.com.au",
    next_invoice: { amount: "A$149.00", date: "1 Aug 2026" },
  },
  usage: [
    { label: "Review drafts", used: 212, cap: 500 },
    { label: "SEO reports", used: 6, cap: 8 },
    { label: "Competitor briefs", used: 4, cap: 5 },
    { label: "Follow-up messages", used: 188, cap: 250 },
  ],
  invoices: [
    { id: "inv_07", date: "1 Jul 2026", amount: "A$149.00", status: "paid" },
    { id: "inv_06", date: "1 Jun 2026", amount: "A$149.00", status: "paid" },
    { id: "inv_05", date: "1 May 2026", amount: "A$149.00", status: "paid" },
  ],
};

/* ------------------------------------------------------------------ */
/* 2. Marco Rossi — Prefecture 48 (Enterprise, $299/mo, 6 venues)      */
/* ------------------------------------------------------------------ */

const marcoDrafts: DraftReview[] = [
  {
    id: "m1", review: "Amazing six-course tasting menu. The somm pairing was perfect.", reviewer: "Alex P", rating: 5, source: "google",
    draft: "Hi Alex, grazie mille for the wonderful review! Chef Marco is delighted you enjoyed the tasting experience. We update the menu seasonally — hope to welcome you back for our spring collection. — Prefecture 48",
    created_at: "2026-07-21T19:30:00+10:00",
  },
  {
    id: "m2", review: "Cocktails were weak and overpriced. Won't be back.", reviewer: "Chris D", rating: 2, source: "google",
    draft: "Hi Chris, we're sorry the cocktails didn't meet your expectations. Our bar team has reviewed the specs and we'd love to invite you back for a complimentary round. Please reach out to our venue manager. — Prefecture 48",
    created_at: "2026-07-21T11:00:00+10:00",
  },
  {
    id: "m3", review: "Best Italian outside of Italy. The burrata is to die for.", reviewer: "Maria L", rating: 5, source: "google",
    draft: "Hi Maria, thank you for the incredible compliment! Our burrata is flown in weekly from Puglia — we're so glad you loved it. See you again soon! — Prefecture 48",
    created_at: "2026-07-20T20:00:00+10:00",
  },
  {
    id: "m4", review: "Service was slow but food made up for it. Will give it another try.", reviewer: "David W", rating: 3, source: "google",
    draft: "Hi David, thanks for your honest feedback. We've added extra floor staff on Friday/Saturday nights to speed up service. Glad the food won you over — we'd love to see you again. — Prefecture 48",
    created_at: "2026-07-20T14:00:00+10:00",
  },
];

const marcoRankings: DualRanking[] = [
  { keyword: "Italian restaurant Sydney", organicThisWeek: 3, organicDelta: 2, localPackThisWeek: 2, localPackDelta: 1 },
  { keyword: "best pasta Sydney", organicThisWeek: 5, organicDelta: -1, localPackThisWeek: 3, localPackDelta: 2 },
  { keyword: "fine dining Sydney", organicThisWeek: 8, organicDelta: 1, localPackThisWeek: 5, localPackDelta: 0 },
  { keyword: "wine bar Surry Hills", organicThisWeek: 2, organicDelta: 1, localPackThisWeek: 1, localPackDelta: 1 },
  { keyword: "private dining room", organicThisWeek: 1, organicDelta: 0, localPackThisWeek: 1, localPackDelta: 0 },
  { keyword: "bottomless brunch", organicThisWeek: 12, organicDelta: -4, localPackThisWeek: 8, localPackDelta: -2 },
];

const marcoCompetitorChanges: CompetitorChange[] = [
  {
    name: "Osteria di Russo",
    domain: "osteriadirusso.com.au",
    threat: "high",
    changes: [
      { type: "menu", description: "New degustation menu launched", oldValue: "5 courses", newValue: "7 courses A$165", timestamp: "4h ago" },
      { type: "hours", description: "Extended dinner hours", oldValue: "Thu–Sat until 10pm", newValue: "Wed–Sun until 11pm", timestamp: "1d ago" },
    ],
  },
  {
    name: "Vino e Cucina",
    domain: "vinoecucina.com.au",
    threat: "medium",
    changes: [
      { type: "price", description: "Pasta prices updated", oldValue: "A$28–38", newValue: "A$32–45", timestamp: "2d ago" },
    ],
  },
  {
    name: "Bar Roma Trattoria",
    domain: "barromasydney.com.au",
    threat: "low",
    changes: [
      { type: "menu", description: "Added gluten-free pasta option", oldValue: "Not offered", newValue: "Available on request", timestamp: "5d ago" },
    ],
  },
];

const marcoLocations: Location[] = [
  { id: "m-loc1", name: "Prefecture 48 — Surry Hills", area: "Surry Hills, NSW", menuSyncTarget: "Google Business Profile + OpenTable", status: "synced", lastSync: "2m ago", targets: [
    { key: "gbp", label: "Google Business Profile", subtitle: "Menu, hours & photos", enabled: true },
    { key: "opentable", label: "OpenTable", subtitle: "42 covers tonight", enabled: true },
    { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
  ]},
  { id: "m-loc2", name: "Prefecture 48 — Barangaroo", area: "Barangaroo, NSW", menuSyncTarget: "Google Business Profile + OpenTable", status: "synced", lastSync: "2m ago", targets: [
    { key: "gbp", label: "Google Business Profile", subtitle: "Menu, hours & photos", enabled: true },
    { key: "opentable", label: "OpenTable", subtitle: "31 covers tonight", enabled: true },
    { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
  ]},
  { id: "m-loc3", name: "Prefecture 48 — Manly", area: "Manly, NSW", menuSyncTarget: "Google Business Profile", status: "synced", lastSync: "8m ago", targets: [
    { key: "gbp", label: "Google Business Profile", subtitle: "Menu, hours & photos", enabled: true },
    { key: "opentable", label: "OpenTable", subtitle: "Not connected", enabled: false },
    { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
  ]},
  { id: "m-loc4", name: "Prefecture 48 — Bondi", area: "Bondi Beach, NSW", menuSyncTarget: "Google Business Profile", status: "synced", lastSync: "15m ago", targets: [
    { key: "gbp", label: "Google Business Profile", subtitle: "Menu, hours & photos", enabled: true },
    { key: "opentable", label: "OpenTable", subtitle: "Not connected", enabled: false },
    { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
  ]},
  { id: "m-loc5", name: "Prefecture 48 — Chatswood", area: "Chatswood, NSW", menuSyncTarget: "Google Business Profile", status: "synced", lastSync: "3h ago", targets: [
    { key: "gbp", label: "Google Business Profile", subtitle: "Menu, hours & photos", enabled: true },
    { key: "website", label: "Website", subtitle: "Auto-embed", enabled: true },
  ]},
  { id: "m-loc6", name: "Prefecture 48 — Newtown", area: "Newtown, NSW", menuSyncTarget: "Not configured", status: "setup_needed", lastSync: "—", targets: [
    { key: "gbp", label: "Google Business Profile", subtitle: "Not connected", enabled: false },
    { key: "website", label: "Website", subtitle: "Auto-embed", enabled: false },
  ]},
];

const marcoPractitioners: Practitioner[] = []; // Hospitality — no practitioners

const marcoClient: Client = {
  id: "c-marco",
  business_name: "Prefecture 48",
  business_type: "Hospitality",
  suburb: "Surry Hills",
  state: "NSW",
  trial_status: "active",
  trial_ends_at: "2026-07-15T00:00:00+10:00",
  card_collected_at: null,
  subscription_status: "trial",
  active_jobs: ["Review Guard", "Menu Sync", "Competitor Watch", "Rank Report"],
  trial_usage: { review_drafts: 5 },
};

const marcoBilling: BillingUsage = {
  plan: {
    name: "Enterprise",
    status: "active",
    price: "A$299 / month",
    renews_at: "15 Aug 2026",
    days_left: 23,
    card: { brand: "Mastercard", last4: "8891", expires: "11 / 2028", valid: true },
    billing_email: "marco@prefecture48.com.au",
    next_invoice: { amount: "A$299.00", date: "15 Aug 2026" },
  },
  usage: [
    { label: "Review drafts", used: 347, cap: 1000 },
    { label: "SEO reports", used: 3, cap: 12 },
    { label: "Competitor briefs", used: 10, cap: 20 },
    { label: "Menu syncs", used: 42, cap: 200 },
  ],
  invoices: [
    { id: "inv_m07", date: "15 Jul 2026", amount: "A$299.00", status: "paid" },
    { id: "inv_m06", date: "15 Jun 2026", amount: "A$299.00", status: "paid" },
    { id: "inv_m05", date: "15 May 2026", amount: "A$299.00", status: "paid" },
  ],
};

/* ------------------------------------------------------------------ */
/* 3. James Mitchell — Parramatta Legal (Trial, 3 days left, no card)  */
/* ------------------------------------------------------------------ */

const jamesDrafts: DraftReview[] = [
  {
    id: "j1", review: "James helped me through a messy property settlement. Professional and fair pricing.", reviewer: "Brenda H", rating: 5, source: "google",
    draft: "Hi Brenda, thank you for your trust during a difficult time. We're glad we could help you reach a fair outcome. If anything else comes up, we're here for you. — Parramatta Legal",
    created_at: "2026-07-22T09:00:00+10:00",
  },
  {
    id: "j2", review: "Never returned my calls. Had to chase them for weeks.", reviewer: "Michael R", rating: 1, source: "google",
    draft: "Hi Michael, I sincerely apologise for the poor communication. We've reviewed our intake process and implemented a 24-hour call-back guarantee. Please give us another chance — I'll personally handle your matter. — James Mitchell, Partner",
    created_at: "2026-07-21T16:00:00+10:00",
  },
];

const jamesRankings: DualRanking[] = [
  { keyword: "family lawyer Parramatta", organicThisWeek: 4, organicDelta: -1, localPackThisWeek: 3, localPackDelta: 0 },
  { keyword: "property settlement lawyer", organicThisWeek: 7, organicDelta: 2, localPackThisWeek: 5, localPackDelta: 2 },
  { keyword: "divorce lawyer Sydney", organicThisWeek: 15, organicDelta: 1, localPackThisWeek: 9, localPackDelta: -2 },
  { keyword: "conveyancing Parramatta", organicThisWeek: 2, organicDelta: 1, localPackThisWeek: 2, localPackDelta: 1 },
];

const jamesCompetitorChanges: CompetitorChange[] = [
  {
    name: "Parramatta Family Law",
    domain: "parrafamilylaw.com.au",
    threat: "high",
    changes: [
      { type: "price", description: "Fixed-fee packages launched", oldValue: "Hourly billing", newValue: "A$2,500–5,500 flat fee", timestamp: "1d ago" },
    ],
  },
];

const jamesLocations: Location[] = [
  { id: "j-loc1", name: "Parramatta Legal — Parramatta", area: "Parramatta, NSW", menuSyncTarget: "Not applicable", status: "synced", lastSync: "—", targets: [] },
];

const jamesPractitioners: Practitioner[] = []; // Legal — no practitioners

const jamesClient: Client = {
  id: "c-james",
  business_name: "Parramatta Legal",
  business_type: "Legal",
  suburb: "Parramatta",
  state: "NSW",
  trial_status: "expiring_soon",
  trial_ends_at: "2026-07-26T00:00:00+10:00",
  card_collected_at: null,
  subscription_status: "trial",
  active_jobs: ["Review Guard", "Rank Report"],
  trial_usage: { review_drafts: 45 },
};

const jamesBilling: BillingUsage = {
  plan: {
    name: "Trial",
    status: "trial",
    price: "Free",
    renews_at: "26 Jul 2026",
    days_left: 3,
    card: null,
    billing_email: "james@parralegal.com.au",
    next_invoice: { amount: "A$149.00", date: "26 Jul 2026" },
  },
  usage: [
    { label: "Review drafts", used: 45, cap: 100 },
    { label: "SEO reports", used: 2, cap: 3 },
  ],
  invoices: [],
};

/* ------------------------------------------------------------------ */
/* 4. Emma Lewis — Surry Hills Physio (Growth, $149/mo)                 */
/* ------------------------------------------------------------------ */

const emmaDrafts: DraftReview[] = [
  {
    id: "e1", review: "Emma fixed my shoulder in 3 sessions. Amazing physio!", reviewer: "Tom H", rating: 5, source: "google",
    draft: "Hi Tom, that's fantastic to hear! Emma's shoulder protocol is one of our most effective. Keep up with those exercises and you'll be back to full strength in no time. — Surry Hills Physio",
    created_at: "2026-07-21T15:00:00+10:00",
  },
  {
    id: "e2", review: "Good treatment but always running 15 mins late.", reviewer: "Priya S", rating: 3, source: "google",
    draft: "Hi Priya, thank you for the feedback. We've introduced a buffer between appointments to reduce wait times. We appreciate your patience and look forward to your next visit. — Surry Hills Physio",
    created_at: "2026-07-20T11:00:00+10:00",
  },
];

const emmaRankings: DualRanking[] = [
  { keyword: "physio Surry Hills", organicThisWeek: 1, organicDelta: 2, localPackThisWeek: 1, localPackDelta: 1 },
  { keyword: "sports physio Sydney", organicThisWeek: 6, organicDelta: 3, localPackThisWeek: 4, localPackDelta: 2 },
  { keyword: "shoulder pain treatment", organicThisWeek: 8, organicDelta: -2, localPackThisWeek: 5, localPackDelta: 0 },
  { keyword: "physio near me", organicThisWeek: 2, organicDelta: 1, localPackThisWeek: 1, localPackDelta: 1 },
];

const emmaCompetitorChanges: CompetitorChange[] = [
  {
    name: "Surry Hills Sports Clinic",
    domain: "surreysportclinic.com.au",
    threat: "medium",
    changes: [
      { type: "hours", description: "Added Saturday appointments", oldValue: "Mon–Fri only", newValue: "Mon–Sat 8–14", timestamp: "3d ago" },
    ],
  },
];

const emmaLocations: Location[] = [
  { id: "e-loc1", name: "Surry Hills Physio — Surry Hills", area: "Surry Hills, NSW", menuSyncTarget: "Not applicable", status: "synced", lastSync: "—", targets: [] },
];

const emmaPractitioners: Practitioner[] = [
  {
    id: "ep1", name: "Emma Lewis", specialty: "Sports physiotherapy",
    lapsed: 18, sent: 12, rebooked: 7, autoFollowUp: true,
    patients: [
      { name: "P. Johnson", lastVisit: "Oct 2025", channel: "SMS", status: "rebooked" },
      { name: "L. Chen", lastVisit: "Sep 2025", channel: "Email", status: "sent" },
      { name: "M. Davis", lastVisit: "Aug 2025", channel: "SMS", status: "queued" },
    ],
  },
  {
    id: "ep2", name: "David Park", specialty: "Rehabilitation",
    lapsed: 11, sent: 6, rebooked: 3, autoFollowUp: false,
    patients: [
      { name: "R. Khan", lastVisit: "Nov 2025", channel: "SMS", status: "rebooked" },
    ],
  },
];

const emmaClient: Client = {
  id: "c-emma",
  business_name: "Surry Hills Physio",
  business_type: "Medical",
  suburb: "Surry Hills",
  state: "NSW",
  trial_status: "active",
  trial_ends_at: "2026-07-15T00:00:00+10:00",
  card_collected_at: null,
  subscription_status: "trial",
  active_jobs: ["Review Guard", "Rebook"],
  trial_usage: { review_drafts: 12 },
};

const emmaBilling: BillingUsage = {
  plan: {
    name: "Growth",
    status: "active",
    price: "A$149 / month",
    renews_at: "5 Aug 2026",
    days_left: 13,
    card: { brand: "Visa", last4: "7890", expires: "03 / 2028", valid: true },
    billing_email: "emma@surreylsphysio.com.au",
    next_invoice: { amount: "A$149.00", date: "5 Aug 2026" },
  },
  usage: [
    { label: "Review drafts", used: 98, cap: 500 },
    { label: "SEO reports", used: 2, cap: 8 },
    { label: "Competitor briefs", used: 1, cap: 5 },
    { label: "Follow-up messages", used: 120, cap: 250 },
  ],
  invoices: [
    { id: "inv_e07", date: "5 Jul 2026", amount: "A$149.00", status: "paid" },
    { id: "inv_e06", date: "5 Jun 2026", amount: "A$149.00", status: "paid" },
  ],
};

/* ------------------------------------------------------------------ */
/* 5. Tom Nguyen — Newtown Fitness Hub (Starter, $79/mo)                */
/* ------------------------------------------------------------------ */

const tomDrafts: DraftReview[] = [
  {
    id: "t1", review: "Great gym, clean equipment, friendly staff. Only downside is parking.", reviewer: "Steve B", rating: 4, source: "google",
    draft: "Hi Steve, thanks for the positive review! We hear you on parking — we've partnered with the council lot on Wilson St for free 2-hour validation. Ask at reception next time. — Newtown Fitness Hub",
    created_at: "2026-07-22T07:00:00+10:00",
  },
  {
    id: "t2", review: "Classes are always fully booked. Impossible to get a spot.", reviewer: "Jess K", rating: 2, source: "google",
    draft: "Hi Jess, we're sorry you've had trouble booking classes. We've added 3 extra HIIT sessions and opened a waitlist feature in our app. Spots now open up automatically — give it a try! — Newtown Fitness Hub",
    created_at: "2026-07-21T12:00:00+10:00",
  },
  {
    id: "t3", review: "PT Tom is incredible! Helped me drop 12kg in 4 months.", reviewer: "Andy L", rating: 5, source: "google",
    draft: "Hi Andy, what an achievement! Tom is thrilled with your progress. Keep up the momentum — we can't wait to see what you accomplish next. — Newtown Fitness Hub",
    created_at: "2026-07-20T08:00:00+10:00",
  },
];

const tomRankings: DualRanking[] = [
  { keyword: "gym Newtown", organicThisWeek: 1, organicDelta: 0, localPackThisWeek: 1, localPackDelta: 0 },
  { keyword: "personal trainer Sydney", organicThisWeek: 14, organicDelta: -2, localPackThisWeek: 12, localPackDelta: -1 },
  { keyword: "fitness classes inner west", organicThisWeek: 3, organicDelta: 1, localPackThisWeek: 2, localPackDelta: 1 },
  { keyword: "24 hour gym", organicThisWeek: 6, organicDelta: 4, localPackThisWeek: 5, localPackDelta: 3 },
];

const tomCompetitorChanges: CompetitorChange[] = [
  {
    name: "Anytime Fitness Newtown",
    domain: "anytimefitness.com.au",
    threat: "high",
    changes: [
      { type: "price", description: "Membership prices reduced", oldValue: "A$89/mo", newValue: "A$69/mo", timestamp: "5d ago" },
    ],
  },
  {
    name: "F45 Newtown",
    domain: "f45training.com.au",
    threat: "medium",
    changes: [
      { type: "menu", description: "New challenge program", oldValue: "8-week challenge", newValue: "6-week summer shred", timestamp: "2d ago" },
    ],
  },
];

const tomLocations: Location[] = [
  { id: "t-loc1", name: "Newtown Fitness Hub — Newtown", area: "Newtown, NSW", menuSyncTarget: "Not applicable", status: "synced", lastSync: "—", targets: [] },
];

const tomPractitioners: Practitioner[] = [];

const tomClient: Client = {
  id: "c-tom",
  business_name: "Newtown Fitness Hub",
  business_type: "Fitness",
  suburb: "Newtown",
  state: "NSW",
  trial_status: "active",
  trial_ends_at: "2026-07-20T00:00:00+10:00",
  card_collected_at: "2026-06-25T00:00:00+10:00",
  subscription_status: "trial",
  active_jobs: ["Review Guard", "Competitor Watch", "Rank Report"],
  trial_usage: { review_drafts: 7 },
};

const tomBilling: BillingUsage = {
  plan: {
    name: "Starter",
    status: "active",
    price: "A$79 / month",
    renews_at: "28 Jul 2026",
    days_left: 5,
    card: { brand: "Amex", last4: "3001", expires: "01 / 2027", valid: true },
    billing_email: "tom@newtownfitness.com.au",
    next_invoice: { amount: "A$79.00", date: "28 Jul 2026" },
  },
  usage: [
    { label: "Review drafts", used: 78, cap: 150 },
    { label: "SEO reports", used: 3, cap: 5 },
    { label: "Competitor briefs", used: 4, cap: 5 },
  ],
  invoices: [
    { id: "inv_t07", date: "28 Jun 2026", amount: "A$79.00", status: "paid" },
    { id: "inv_t06", date: "28 May 2026", amount: "A$79.00", status: "paid" },
  ],
};

/* ------------------------------------------------------------------ */
/* Persona registry                                                        */
/* ------------------------------------------------------------------ */

export const PERSONAS: Record<PersonaId, Persona> = {
  "sarah-chen": {
    id: "sarah-chen",
    name: "Dr Sarah Chen",
    businessName: "Bondi Dental Clinic",
    vertical: "Dental",
    suburb: "Bondi Junction",
    state: "NSW",
    plan: "Growth",
    planStatus: "active",
    trialEndsAt: "2026-07-15T00:00:00+10:00",
    cardCollectedAt: null,
    jobs: ["Review Guard", "Rebook", "Rank Report"],
    billing: sarahBilling,
    drafts: sarahDrafts,
    rankings: sarahRankings,
    competitorChanges: sarahCompetitorChanges,
    locations: sarahLocations,
    practitioners: sarahPractitioners,
    client: sarahClient,
  },
  "marco-rossi": {
    id: "marco-rossi",
    name: "Marco Rossi",
    businessName: "Prefecture 48",
    vertical: "Hospitality",
    suburb: "Surry Hills",
    state: "NSW",
    plan: "Enterprise",
    planStatus: "active",
    trialEndsAt: "2026-07-15T00:00:00+10:00",
    cardCollectedAt: null,
    jobs: ["Review Guard", "Menu Sync", "Competitor Watch", "Rank Report"],
    billing: marcoBilling,
    drafts: marcoDrafts,
    rankings: marcoRankings,
    competitorChanges: marcoCompetitorChanges,
    locations: marcoLocations,
    practitioners: marcoPractitioners,
    client: marcoClient,
  },
  "james-mitchell": {
    id: "james-mitchell",
    name: "James Mitchell",
    businessName: "Parramatta Legal",
    vertical: "Legal",
    suburb: "Parramatta",
    state: "NSW",
    plan: "Trial",
    planStatus: "trial",
    trialEndsAt: "2026-07-26T00:00:00+10:00",
    cardCollectedAt: null,
    jobs: ["Review Guard", "Rank Report"],
    billing: jamesBilling,
    drafts: jamesDrafts,
    rankings: jamesRankings,
    competitorChanges: jamesCompetitorChanges,
    locations: jamesLocations,
    practitioners: jamesPractitioners,
    client: jamesClient,
  },
  "emma-lewis": {
    id: "emma-lewis",
    name: "Emma Lewis",
    businessName: "Surry Hills Physio",
    vertical: "Medical",
    suburb: "Surry Hills",
    state: "NSW",
    plan: "Growth",
    planStatus: "active",
    trialEndsAt: "2026-07-15T00:00:00+10:00",
    cardCollectedAt: null,
    jobs: ["Review Guard", "Rebook"],
    billing: emmaBilling,
    drafts: emmaDrafts,
    rankings: emmaRankings,
    competitorChanges: emmaCompetitorChanges,
    locations: emmaLocations,
    practitioners: emmaPractitioners,
    client: emmaClient,
  },
  "tom-nguyen": {
    id: "tom-nguyen",
    name: "Tom Nguyen",
    businessName: "Newtown Fitness Hub",
    vertical: "Fitness",
    suburb: "Newtown",
    state: "NSW",
    plan: "Starter",
    planStatus: "active",
    trialEndsAt: "2026-07-20T00:00:00+10:00",
    cardCollectedAt: "2026-06-25T00:00:00+10:00",
    jobs: ["Review Guard", "Competitor Watch", "Rank Report"],
    billing: tomBilling,
    drafts: tomDrafts,
    rankings: tomRankings,
    competitorChanges: tomCompetitorChanges,
    locations: tomLocations,
    practitioners: tomPractitioners,
    client: tomClient,
  },
};

/** Default persona shown on first load. */
export const DEFAULT_PERSONA_ID: PersonaId = "sarah-chen";

/** Ordered list of persona entries for the switcher dropdown. */
export const PERSONA_LIST: { id: PersonaId; name: string; businessName: string; plan: string }[] = [
  { id: "sarah-chen", name: "Dr Sarah Chen", businessName: "Bondi Dental Clinic", plan: "Growth" },
  { id: "marco-rossi", name: "Marco Rossi", businessName: "Prefecture 48", plan: "Enterprise" },
  { id: "james-mitchell", name: "James Mitchell", businessName: "Parramatta Legal", plan: "Trial" },
  { id: "emma-lewis", name: "Emma Lewis", businessName: "Surry Hills Physio", plan: "Growth" },
  { id: "tom-nguyen", name: "Tom Nguyen", businessName: "Newtown Fitness Hub", plan: "Starter" },
];
