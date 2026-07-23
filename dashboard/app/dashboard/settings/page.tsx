"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  CreditCard,
  Gauge,
  Settings,
  Save,
  X,
  ExternalLink,
  Download,
  Check,
  ShieldCheck,
  FileText,
  Search,
  MessageSquare,
  ChevronRight,
  TrendingUp,
} from "lucide-react";
import Toggle from "@/components/Toggle";
import { api } from "@/lib/api";
import { stubBillingUsage } from "@/lib/stubs";
import type { BillingUsage, Invoice, UsageBar } from "@/lib/stubs";
import {
  usagePercent,
  usageStatus,
  usageRemaining,
  STATUS_STYLES,
} from "@/lib/usage";
import type { LucideIcon } from "lucide-react";

type SettingsTab = "preferences" | "billing" | "usage";

const JOBS = [
  "Review Guard",
  "Rank Report",
  "Competitor Watch",
  "Rebook",
  "Menu Sync",
];

const JOB_ICONS: Record<string, LucideIcon> = {
  "Review drafts": ShieldCheck,
  "SEO reports": FileText,
  "Competitor briefs": Search,
  "Follow-up messages": MessageSquare,
  "Menu syncs": Settings,
};

const INVOICE_STATUS_STYLES: Record<Invoice["status"], string> = {
  paid: "bg-chart-3/10 text-chart-3",
  open: "bg-muted text-chart-2",
  void: "bg-destructive/10 text-destructive",
};

/* ------------------------------------------------------------------ */
/* Tab: Preferences                                                     */
/* ------------------------------------------------------------------ */

function PreferencesTab() {
  const [jobToggles, setJobToggles] = useState<Record<string, boolean>>({
    "Review Guard": true,
    "Rank Report": true,
    "Competitor Watch": false,
    Rebook: false,
    "Menu Sync": false,
  });
  const [voiceSample, setVoiceSample] = useState(
    "Hi, this is Dr Chen from Bondi Dental. We care about your smile and want to make sure every visit is comfortable. Please let us know how we did today."
  );
  const [keywords, setKeywords] = useState([
    "dentist Bondi",
    "teeth whitening Sydney",
    "emergency dentist",
    "dental implant",
    "invisalign",
  ]);
  const [keywordInput, setKeywordInput] = useState("");
  const [competitorUrls, setCompetitorUrls] = useState([
    "https://bondibeachdental.com.au",
    "https://sydneysmiles.com.au",
  ]);
  const [urlInput, setUrlInput] = useState("");

  const addKeyword = () => {
    const kw = keywordInput.trim();
    if (kw && !keywords.includes(kw)) setKeywords([...keywords, kw]);
    setKeywordInput("");
  };
  const removeKeyword = (kw: string) =>
    setKeywords(keywords.filter((k) => k !== kw));
  const addUrl = () => {
    const url = urlInput.trim();
    if (url && !competitorUrls.includes(url))
      setCompetitorUrls([...competitorUrls, url]);
    setUrlInput("");
  };
  const removeUrl = (url: string) =>
    setCompetitorUrls(competitorUrls.filter((u) => u !== url));

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        {/* Active Jobs */}
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
          <h2 className="text-lg font-semibold text-foreground">Active Jobs</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Toggle automations on/off
          </p>
          <div className="space-y-3">
            {JOBS.map((job) => (
              <label
                key={job}
                className="flex items-center justify-between"
              >
                <span className="text-sm font-medium text-muted-foreground">
                  {job}
                </span>
                <Toggle
                  checked={jobToggles[job]}
                  onChange={(v) => setJobToggles({ ...jobToggles, [job]: v })}
                  aria-label={`Toggle ${job}`}
                />
              </label>
            ))}
          </div>
        </div>

        {/* Voice Sample */}
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
          <h2 className="text-lg font-semibold text-foreground">
            Voice Sample
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Used for AI-generated phone scripts
          </p>
          <textarea
            className="w-full rounded-lg border border-border bg-background p-3 text-sm"
            rows={5}
            value={voiceSample}
            onChange={(e) => setVoiceSample(e.target.value)}
          />
        </div>

        {/* SEO Keywords */}
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
          <h2 className="text-lg font-semibold text-foreground">
            SEO Keywords
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Keywords to track in rankings
          </p>
          <div className="mb-3 flex gap-2">
            <input
              type="text"
              className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-sm"
              placeholder="Add keyword..."
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addKeyword()}
            />
            <button
              onClick={addKeyword}
              className="rounded-lg bg-muted px-3 py-1.5 text-sm font-medium hover:bg-muted/80"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((kw) => (
              <span
                key={kw}
                className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent"
              >
                {kw}
                <button
                  onClick={() => removeKeyword(kw)}
                  className="text-accent/50 hover:text-accent"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Competitor URLs */}
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
          <h2 className="text-lg font-semibold text-foreground">
            Competitor URLs
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Sites to monitor for changes
          </p>
          <div className="mb-3 flex gap-2">
            <input
              type="text"
              className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-sm"
              placeholder="https://..."
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addUrl()}
            />
            <button
              onClick={addUrl}
              className="rounded-lg bg-muted px-3 py-1.5 text-sm font-medium hover:bg-muted/80"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {competitorUrls.map((url) => (
              <span
                key={url}
                className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-chart-2"
              >
                {url.replace("https://", "")}
                <button
                  onClick={() => removeUrl(url)}
                  className="text-chart-2/50 hover:text-chart-2"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={() => toast.info("Settings saved (demo mode)")}
        className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/90 transition-colors"
      >
        <Save className="h-4 w-4" /> Save Settings
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tab: Billing                                                         */
/* ------------------------------------------------------------------ */

function BillingTab({ billing, portalLoading }: { billing: BillingUsage; portalLoading: boolean }) {
  const { plan, usage, invoices } = billing;

  const openPortal = async () => {
    try {
      const res = await api.post<{ url: string }>("/billing/portal", {});
      if (res?.url) window.location.href = res.url;
    } catch {
      toast.info("Stripe portal coming soon (demo mode)");
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        {/* Current plan */}
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Current plan
              </p>
              <p className="mt-1 text-2xl font-semibold text-foreground">
                {plan.name}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {plan.price} &middot; renews {plan.renews_at}
              </p>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-chart-3/10 px-2 py-0.5 text-xs font-medium text-chart-3">
              <Check className="h-3.5 w-3.5" /> Active
            </span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              onClick={openPortal}
              disabled={portalLoading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/90 disabled:opacity-60 transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
              {portalLoading ? "Opening…" : "Manage billing"}
            </button>
            <button
              onClick={() => toast.info("Plan changes coming soon")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
            >
              Change plan
            </button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Opens the secure Stripe billing portal to update payment, download
            invoices, or cancel.
          </p>
        </div>

        {/* Payment method */}
        <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            Payment method
          </h2>
          {plan.card ? (
            <div className="flex items-center justify-between rounded-lg border border-border bg-muted p-4">
              <div className="flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {plan.card.brand} •••• {plan.card.last4}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Expires {plan.card.expires}
                  </p>
                </div>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-chart-3/10 px-2 py-0.5 text-xs font-medium text-chart-3">
                Valid
              </span>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-muted p-4 text-sm text-muted-foreground">
              No payment method on file.
            </div>
          )}
          <div className="mt-3 flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Billing email</span>
            <span className="text-sm font-medium text-foreground">
              {plan.billing_email}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Next invoice</span>
            <span className="text-sm font-medium text-foreground">
              {plan.next_invoice.amount} on {plan.next_invoice.date}
            </span>
          </div>
        </div>
      </div>

      {/* Plan usage */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-6">
        <h2 className="mb-3 text-lg font-semibold text-foreground">
          Plan usage this cycle
        </h2>
        <div className="divide-y divide-border">
          {usage.map((bar) => (
            <BillingUsageRow key={bar.label} bar={bar} />
          ))}
        </div>
      </div>

      {/* Recent invoices */}
      <div className="overflow-hidden rounded-xl ring-1 ring-foreground/10 bg-background">
        <div className="border-b border-border p-4">
          <h2 className="text-lg font-semibold text-foreground">
            Recent invoices
          </h2>
        </div>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {invoices.length === 0 ? (
              <tr>
                <td colSpan={4} className="p-6 text-center text-sm text-muted-foreground">
                  No invoices yet — your first invoice will appear after your next billing cycle.
                </td>
              </tr>
            ) : (
              invoices.map((inv) => (
                <tr
                  key={inv.id}
                  className="border-b border-border last:border-0 hover:bg-muted"
                >
                  <td className="px-4 py-3 font-medium text-foreground">{inv.date}</td>
                  <td className="px-4 py-3 text-muted-foreground">{inv.amount}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${INVOICE_STATUS_STYLES[inv.status]}`}
                    >
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => toast.info("PDF download coming soon")}
                      className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                    >
                      <Download className="h-3.5 w-3.5" /> PDF
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tab: Usage                                                           */
/* ------------------------------------------------------------------ */

function UsageTab({ billing }: { billing: BillingUsage }) {
  const { plan, usage } = billing;

  return (
    <div className="space-y-6">
      {/* Plan card */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl ring-1 ring-foreground/10 bg-background p-4">
        <div className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-[0.9375rem] font-semibold text-foreground">
              {plan.name} plan
            </p>
            <p className="text-xs text-muted-foreground">
              Billing cycle resets {plan.renews_at} &middot; {plan.days_left}{" "}
              days left
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-chart-3/10 px-2 py-0.5 text-xs font-medium text-chart-3">
          Active
        </span>
      </div>

      {/* Usage bars */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-background">
        <div className="border-b border-border p-4">
          <h2 className="text-lg font-semibold text-foreground">This cycle</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Used / cap / remaining per job
          </p>
        </div>
        <div className="divide-y divide-border">
          {usage.map((bar) => (
            <UsageDetailRow key={bar.label} bar={bar} />
          ))}
        </div>
      </div>

      {/* Need higher caps */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-background p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">
              Need higher caps?
            </span>
          </div>
          <button
            onClick={() => toast.info("Plan comparison coming soon")}
            className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
          >
            Compare plans <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Settings Page                                                    */
/* ------------------------------------------------------------------ */

export default function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>("preferences");
  const [billing, setBilling] = useState<BillingUsage>(stubBillingUsage);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);

  useEffect(() => {
    api
      .get<BillingUsage>("/billing/usage")
      .then((data) => setBilling(data ?? stubBillingUsage))
      .catch(() => setBilling(stubBillingUsage))
      .finally(() => setLoading(false));
  }, []);

  const tabDefs: { id: SettingsTab; label: string; icon: typeof Settings }[] = [
    { id: "preferences", label: "Preferences", icon: Settings },
    { id: "billing", label: "Billing", icon: CreditCard },
    { id: "usage", label: "Usage & Caps", icon: Gauge },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage your preferences, billing, and usage
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-4 border-b border-border">
        {tabDefs.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-1.5 pb-2 text-sm font-medium transition-colors ${
                tab === t.id
                  ? "border-b-2 border-accent text-accent"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      ) : (
        <>
          {tab === "preferences" && <PreferencesTab />}
          {tab === "billing" && (
            <BillingTab billing={billing} portalLoading={portalLoading} />
          )}
          {tab === "usage" && <UsageTab billing={billing} />}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Shared sub-components                                                */
/* ------------------------------------------------------------------ */

function BillingUsageRow({ bar }: { bar: UsageBar }) {
  const status = usageStatus(bar);
  const pct = usagePercent(bar);
  const styles = STATUS_STYLES[status];

  return (
    <div className="py-3">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm text-foreground">{bar.label}</span>
        <span className="font-mono text-xs text-muted-foreground">
          {bar.used}/{bar.cap}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-input">
        <div
          className={`h-full rounded-full ${styles.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function UsageDetailRow({ bar }: { bar: UsageBar }) {
  const status = usageStatus(bar);
  const pct = usagePercent(bar);
  const remaining = usageRemaining(bar);
  const styles = STATUS_STYLES[status];
  const Icon = JOB_ICONS[bar.label];

  return (
    <div className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
          <span className="text-sm font-medium text-foreground">
            {bar.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${styles.badge}`}
          >
            {styles.label}
          </span>
          <span className="font-mono text-sm">
            <strong className="font-semibold text-foreground">{bar.used}</strong>
            <span className="text-muted-foreground">/{bar.cap}</span>
          </span>
        </div>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-input">
        <div
          className={`h-full rounded-full ${styles.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        {remaining} of quota remaining this cycle
      </p>
    </div>
  );
}
