import {
  MessageSquare,
  BarChart3,
  Eye,
  CalendarHeart,
  Utensils,
  Check,
} from "lucide-react";

const features = [
  {
    name: "Review Guard",
    price: "$149–$249/mo",
    icon: MessageSquare,
    description:
      "Every Google & Yelp review answered within hours, drafted in your own voice by Claude. You approve before anything goes out. Never write a manual reply again.",
    bullets: [
      "Webhook + 24-hour Yelp polling",
      "AU English, no robotic phrases",
      "Approve / discard from your dashboard",
    ],
  },
  {
    name: "Rank Report",
    price: "$99–$199/mo",
    icon: BarChart3,
    description:
      "Monday 6am AEST, you get a plain-English email showing where you rank for the keywords that matter in your suburb. No jargon — just what moved and what to do.",
    bullets: [
      "5 keywords per client tracked",
      "Mobile-first, Australia/Sydney search",
      "Weekly via email + dashboard",
    ],
  },
  {
    name: "Competitor Watch",
    price: "$199–$299/mo",
    icon: Eye,
    description:
      "Every Sunday night we snapshot your competitors' websites. When something changes — a new offer, a price drop, a blog post — you get a threat-rated brief by 7am Monday.",
    bullets: [
      "Website snapshot + diff detection",
      "Claude-generated competitive brief",
      "Threat level: Low / Medium / High",
    ],
  },
  {
    name: "Rebook",
    price: "$299–$499/mo",
    icon: CalendarHeart,
    description:
      "Identify patients 60 days since last visit, send a follow-up SMS in your tone, gate sends on AU public holidays. Works with Cliniko and Square.",
    bullets: [
      "SMS via Twilio, AU numbers",
      "Public holiday & do-not-contact gate",
      "Cliniko + Square booking integrations",
    ],
  },
  {
    name: "Menu Sync",
    price: "$149/mo",
    icon: Utensils,
    description:
      "Edit your menu in one place. We push it to Google Business Profile and Square Catalog automatically. No more out-of-date prices across platforms.",
    bullets: [
      "GBP Menu API + Square Catalog",
      "Sync log + error handling",
      "Pure integration, no AI drift",
    ],
  },
];

const steps = [
  {
    number: 1,
    title: "Sign up",
    text: "Enter your business name, suburb, and pick the jobs you want. No card needed for 14 days.",
  },
  {
    number: 2,
    title: "Connect Google & tools",
    text: "Approve GBP OAuth for reviews. Tell us your keywords, competitors, or booking system — done in two minutes.",
  },
  {
    number: 3,
    title: "Approve drafts",
    text: "We work in the background. Drop into your dashboard once a week to approve review replies and read reports.",
  },
];

const tiers = [
  {
    name: "Starter",
    price: "$99",
    tagline: "For small operators testing the waters.",
    includes: ["Rank Report"],
    highlighted: false,
  },
  {
    name: "Growth",
    price: "$249",
    tagline: "The background operator that keeps you sorted.",
    includes: ["Review Guard", "Rank Report", "Competitor Watch"],
    highlighted: true,
  },
  {
    name: "Complete",
    price: "$499",
    tagline: "Everything, set-and-forget.",
    includes: [
      "Review Guard",
      "Rank Report",
      "Competitor Watch",
      "Rebook",
      "Menu Sync",
    ],
    highlighted: false,
  },
];

const faqs = [
  {
    q: "Do I need to give LocalMate my credit card?",
    a: "No. The 14-day trial unlocks all features with zero card required. We'll prompt you to add a card on day 12 — only charged after the trial ends.",
  },
  {
    q: "What happens after the trial?",
    a: "Add a card before day 14 and your trial converts to a paid subscription. Don't add one and your account reverts to read-only — we keep your data for 30 days in case you change your mind.",
  },
  {
    q: "Is this really AI writing my reviews?",
    a: "Claude Haiku 4.5 drafts every reply in the voice you give us — three sentences in your own words at signup. You approve every reply before it goes out. Nothing is auto-posted.",
  },
  {
    q: "What if my competitors change their website overnight?",
    a: "We snapshot their pages every Sunday at 10pm AEST. If anything changes by Monday 6am, you get a threat-rated brief in your inbox and dashboard.",
  },
  {
    q: "Do you support Cliniko and Square for the rebooking job?",
    a: "Yes. Cliniko is live today; Square Bookings API is live today. Nookal, Halaxy and Mindbody are on the roadmap for Q2 2026.",
  },
  {
    q: "How do you handle AU public holidays?",
    a: "Every SMS and email job checks against your state's calendar (NSW, VIC, QLD, WA, SA, TAS, ACT, NT) via the workalendar library. We don't send on public holidays.",
  },
];

export default function MarketingLanding() {
  return (
    <>
      <header className="sticky top-0 z-50 bg-background/90 backdrop-blur-md border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-amber-600 text-xs font-bold text-white">
              LM
            </div>
            <span className="text-xl font-bold text-foreground">
              Local<span className="text-accent">Mate</span>
            </span>
          </a>
          <div className="flex items-center gap-4">
            <a
              href="/demo"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Demo
            </a>
            <a
              href="/login"
              className="bg-primary text-primary-foreground rounded-lg px-4 py-2 text-sm font-semibold hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              Start free trial
            </a>
          </div>
        </div>
      </header>

      <main id="main-content">
        <section className="max-w-7xl mx-auto px-6 pt-16 pb-12 text-center">
          <span className="bg-accent/10 text-accent rounded-full px-3 py-1 text-xs font-medium">
            Built for Aussie small businesses
          </span>
          <h1 className="mt-6 text-3xl sm:text-4xl md:text-[48px] font-bold tracking-tight leading-tight">
            Automate your reviews, SEO, and customers — without lifting a finger.
          </h1>
          <p className="max-w-2xl mx-auto text-lg text-muted-foreground mt-6">
            LocalMate runs five background jobs that keep your local biz sorted:
            review replies, ranking reports, competitor alerts, patient rebooking,
            and menu sync. 14-day free trial, no card required.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3 mt-8">
            <a
              href="/login"
              className="bg-primary text-primary-foreground rounded-lg px-6 py-3 font-semibold hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              Start your 14-day free trial
            </a>
            <a
              href="/demo"
              className="border border-border rounded-lg px-6 py-3 font-semibold hover:border-accent transition-colors"
            >
              See it in action
            </a>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-4 mt-6 text-sm text-muted-foreground">
            <span>No credit card</span>
            <span className="text-border">|</span>
            <span>Cancel anytime</span>
            <span className="text-border">|</span>
            <span>AU support, AEST hours</span>
          </div>
        </section>

        <section className="bg-primary text-primary-foreground py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 max-w-5xl mx-auto px-6 gap-8">
            <div>
              <span className="text-4xl font-bold block">&lt;300ms</span>
              <span className="text-sm text-primary-foreground/70 mt-2 block">
                Avg review reply time, drafted by Claude Haiku 4.5
              </span>
            </div>
            <div>
              <span className="text-4xl font-bold block">5 jobs</span>
              <span className="text-sm text-primary-foreground/70 mt-2 block">
                Running in the background while you serve customers
              </span>
            </div>
            <div>
              <span className="text-4xl font-bold block">14 days</span>
              <span className="text-sm text-primary-foreground/70 mt-2 block">
                Free trial with full access, no card required
              </span>
            </div>
            <div>
              <span className="text-4xl font-bold block">$0</span>
              <span className="text-sm text-primary-foreground/70 mt-2 block">
                Setup cost. Cancel anytime.
              </span>
            </div>
          </div>
        </section>

        <section className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-center">
            <span className="text-accent text-sm font-semibold uppercase tracking-wider">
              Features
            </span>
            <h2 className="mt-2 text-3xl font-bold">
              Five jobs that sort your local biz, no dramas.
            </h2>
            <p className="max-w-2xl mx-auto text-muted-foreground mt-4">
              Each job runs on its own schedule. Pick the ones you need. Cancel
              the ones you don&apos;t.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mt-12">
            {features.map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.name}
                  className="bg-background border border-border rounded-xl p-6 hover:border-accent/30 hover:shadow-lg transition-all"
                >
                  <div className="h-10 w-10 rounded-lg bg-accent/10 text-accent flex items-center justify-center">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex items-center gap-2 mt-4">
                    <h3 className="text-lg font-semibold">{feat.name}</h3>
                    <span className="bg-muted text-muted-foreground text-xs px-2 py-1 rounded-full">
                      {feat.price}
                    </span>
                  </div>
                  <p className="text-muted-foreground text-sm mt-2">
                    {feat.description}
                  </p>
                  <ul className="mt-4 space-y-1.5 text-sm text-muted-foreground">
                    {feat.bullets.map((b) => (
                      <li key={b} className="flex items-start gap-1.5">
                        <span aria-hidden="true">•</span> {b}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </section>

        <section className="bg-muted/30 py-16">
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center">
              <span className="text-accent text-sm font-semibold uppercase tracking-wider">
                How it works
              </span>
              <h2 className="mt-2 text-3xl font-bold">
                Live in 3 steps. 5 minutes a week.
              </h2>
            </div>
            <div className="grid md:grid-cols-3 gap-8 mt-12">
              {steps.map((step) => (
                <div key={step.number} className="text-center">
                  <div className="mx-auto h-12 w-12 rounded-full bg-accent text-accent-foreground flex items-center justify-center text-xl font-bold">
                    {step.number}
                  </div>
                  <h3 className="mt-6 font-semibold text-lg">{step.title}</h3>
                  <p className="mt-2 text-muted-foreground">{step.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-center">
            <span className="text-accent text-sm font-semibold uppercase tracking-wider">
              Pricing
            </span>
            <h2 className="mt-2 text-3xl font-bold">
              One subscription. Pay per job.
            </h2>
            <p className="max-w-2xl mx-auto text-muted-foreground mt-4">
              No setup fees. No lock-in. 14-day free trial with full access — no
              card required.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8 mt-12">
            {tiers.map((tier) => (
              <div
                key={tier.name}
                className={`bg-background border rounded-xl p-8 relative ${
                  tier.highlighted
                    ? "border-accent ring-2 ring-accent/30"
                    : "border-border"
                }`}
              >
                {tier.highlighted && (
                  <span className="bg-accent text-accent-foreground text-xs px-3 py-1 rounded-full absolute -top-3 right-6 font-medium">
                    Most popular
                  </span>
                )}
                <h3 className="text-xl font-semibold">{tier.name}</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {tier.tagline}
                </p>
                <div className="mt-4">
                  <span className="text-4xl font-bold">{tier.price}</span>
                  <span className="text-base font-normal text-muted-foreground">
                    /month AUD
                  </span>
                </div>
                <ul className="mt-6 space-y-2 text-sm text-muted-foreground">
                  {tier.includes.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <Check className="h-4 w-4 text-accent mt-0.5 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
                <a
                  href="/login"
                  className={`mt-6 block w-full text-center rounded-lg py-3 font-semibold transition-colors ${
                    tier.highlighted
                      ? "bg-primary text-primary-foreground hover:bg-accent hover:text-accent-foreground"
                      : "border border-border hover:border-accent"
                  }`}
                >
                  Start free trial
                </a>
              </div>
            ))}
          </div>
          <div className="bg-muted rounded-xl p-6 mt-12 text-center text-sm text-muted-foreground">
            All plans include 14-day free trial, no card required. Cancel
            anytime. Australian support, AEST business hours.
          </div>
        </section>

        <section className="max-w-3xl mx-auto px-6 py-16">
          <div className="text-center">
            <h2 className="text-3xl font-bold">Questions, sorted.</h2>
          </div>
          <div className="mt-12 divide-y divide-border">
            {faqs.map((faq) => (
              <details key={faq.q}>
                <summary className="cursor-pointer py-4 text-lg font-semibold list-none">
                  {faq.q}
                </summary>
                <p className="text-muted-foreground mt-3 pb-4">{faq.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="bg-primary text-primary-foreground py-16">
          <div className="max-w-7xl mx-auto px-6 text-center">
            <h2 className="text-3xl font-bold">
              Stop spending your evenings on reviews and reports.
            </h2>
            <p className="text-primary-foreground/80 mt-4">
              Start your 14-day free trial. No card, no lock-in.
            </p>
            <a
              href="/login"
              className="inline-block bg-accent text-accent-foreground rounded-lg px-6 py-3 font-semibold mt-8 hover:bg-accent-foreground hover:text-accent transition-colors"
            >
              Start your free trial
            </a>
          </div>
        </section>

        <footer className="border-t border-border bg-background py-12">
          <div className="max-w-7xl mx-auto px-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              <div className="col-span-2 md:col-span-1">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-amber-600 text-xs font-bold text-white">
                    LM
                  </div>
                  <span className="text-xl font-bold text-foreground">
                    Local<span className="text-accent">Mate</span>
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mt-3">
                  Automation for Aussie SMBs.
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  A product by CrewCircle. Made in Sydney.
                </p>
              </div>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3">
                  Products
                </h3>
                <ul className="space-y-2">
                  {features.map((f) => (
                    <li key={f.name}>
                      <a
                        href="#features"
                        className="text-sm text-muted-foreground hover:text-foreground"
                      >
                        {f.name}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3">
                  Company
                </h3>
                <ul className="space-y-2">
                  <li>
                    <a
                      href="https://crewcircle.com.au"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      CrewCircle
                    </a>
                  </li>
                  <li>
                    <a
                      href="/demo"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Demo
                    </a>
                  </li>
                  <li>
                    <a
                      href="/login"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Login
                    </a>
                  </li>
                  <li>
                    <a
                      href="/login"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Sign up
                    </a>
                  </li>
                </ul>
              </div>
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3">
                  Legal
                </h3>
                <ul className="space-y-2">
                  <li>
                    <a
                      href="#"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Privacy
                    </a>
                  </li>
                  <li>
                    <a
                      href="#"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Terms
                    </a>
                  </li>
                  <li>
                    <a
                      href="/#pricing"
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Pricing
                    </a>
                  </li>
                </ul>
              </div>
            </div>
            <div className="border-t border-border pt-6 mt-8 flex flex-col sm:flex-row justify-between gap-2 text-xs text-muted-foreground">
              <span>&copy; 2026 CrewCircle</span>
              <span>Proudly built in Sydney, Australia.</span>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
