"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  CreditCard,
  Check,
  ExternalLink,
  Download,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { stubBillingUsage } from "@/lib/stubs";
import type { BillingUsage, Invoice, UsageBar } from "@/lib/stubs";
import { usagePercent, usageStatus, STATUS_STYLES } from "@/lib/usage";

const INVOICE_STATUS_STYLES: Record<Invoice["status"], string> = {
  paid: "bg-chart-3/10 text-chart-3",
  open: "bg-muted text-chart-2",
  void: "bg-destructive/10 text-destructive",
};

export default function BillingPage() {
  const [billing, setBilling] = useState<BillingUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);

  useEffect(() => {
    api
      .get<BillingUsage>("/billing/usage")
      .then((data) => setBilling(data ?? stubBillingUsage))
      .catch(() => setBilling(stubBillingUsage))
      .finally(() => setLoading(false));
  }, []);

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const res = await api.post<{ url: string }>("/billing/portal", {});
      if (res?.url) window.location.href = res.url;
    } finally {
      setPortalLoading(false);
    }
  };

  if (loading || !billing) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  const { plan, usage, invoices } = billing;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Billing</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage your plan, payment method and invoices
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Current plan */}
        <div className="rounded-lg border border-border bg-background p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Current plan
              </p>
              <p className="mt-1 text-2xl font-bold text-foreground">
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
              className="inline-flex items-center gap-1 rounded bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/90 disabled:opacity-60"
            >
              <ExternalLink className="h-4 w-4" />
              {portalLoading ? "Opening…" : "Manage billing"}
            </button>
            <button className="inline-flex items-center gap-1 rounded border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted">
              Change plan
            </button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Opens the secure Stripe billing portal to update payment, download
            invoices, or cancel.
          </p>
        </div>

        {/* Payment method */}
        <div className="rounded-lg border border-border bg-background p-6">
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

      {/* Plan usage this cycle */}
      <div className="rounded-lg border border-border bg-background p-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            Plan usage this cycle
          </h2>
          <Link
            href="/dashboard/usage"
            className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
          >
            View details <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <div className="divide-y divide-border">
          {usage.map((bar) => (
            <UsageSummaryRow key={bar.label} bar={bar} />
          ))}
        </div>
      </div>

      {/* Recent invoices */}
      <div className="overflow-hidden rounded-lg border border-border bg-background">
        <div className="border-b border-border p-4">
          <h2 className="text-lg font-semibold text-foreground">
            Recent invoices
          </h2>
        </div>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <th className="p-4 font-medium">Date</th>
              <th className="p-4 font-medium">Amount</th>
              <th className="p-4 font-medium">Status</th>
              <th className="p-4" />
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr
                key={inv.id}
                className="border-b border-border last:border-0 hover:bg-muted"
              >
                <td className="p-4 font-medium text-foreground">{inv.date}</td>
                <td className="p-4 text-muted-foreground">{inv.amount}</td>
                <td className="p-4">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${INVOICE_STATUS_STYLES[inv.status]}`}
                  >
                    {inv.status}
                  </span>
                </td>
                <td className="p-4 text-right">
                  <button className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
                    <Download className="h-3.5 w-3.5" /> PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function UsageSummaryRow({ bar }: { bar: UsageBar }) {
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
