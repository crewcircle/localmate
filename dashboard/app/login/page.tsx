"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

const businessTypes = [
  "Dental",
  "Restaurant",
  "Gym",
  "Salon",
  "Physio",
  "Cafe",
  "Tradie",
];

const states = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];

const jobOptions = [
  { name: "Review Guard", value: "review_guard" },
  { name: "Rank Report", value: "rank_report" },
  { name: "Competitor Watch", value: "competitor_watch" },
  { name: "Rebook", value: "rebook" },
  { name: "Menu Sync", value: "menu_sync" },
];

export default function LoginPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const form = new FormData(e.currentTarget);
    const selectedJobs = form.getAll("jobs").map((j) => j as string);

    const payload = {
      business_name: form.get("business_name"),
      business_type: form.get("business_type"),
      email: form.get("email"),
      suburb: form.get("suburb"),
      state: form.get("state"),
      selected_jobs: selectedJobs,
    };

    const result = await api.post<{
      client_id: string;
      trial_ends_at: string;
    }>("/auth/signup", payload);

    setSubmitting(false);

    if (result) {
      router.push("/dashboard");
    } else {
      setError(
        "Sign-up failed. Backend endpoint may not be configured or email already in use."
      );
    }
  }

  return (
    <main id="main-content">
      <div className="max-w-md mx-auto py-16 px-6">
        <div className="bg-background border border-border rounded-xl p-8 shadow-sm">
          <div className="flex flex-col items-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-amber-600 text-sm font-bold text-white">
              LM
            </div>
            <span className="mt-2 text-xl font-bold text-foreground">
              Local<span className="text-accent">Mate</span>
            </span>
          </div>

          <h1 className="mt-6 text-2xl font-bold text-center">
            Start your 14-day free trial
          </h1>
          <p className="text-muted-foreground text-sm mt-1 text-center">
            No card required. Cancel anytime.
          </p>

          <form onSubmit={onSubmit} className="mt-6 grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label
                htmlFor="business_name"
                className="block text-sm font-medium mb-1"
              >
                Business name
              </label>
              <input
                id="business_name"
                name="business_name"
                type="text"
                required
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"
                placeholder="e.g. Bondi Dental Clinic"
              />
            </div>

            <div>
              <label
                htmlFor="business_type"
                className="block text-sm font-medium mb-1"
              >
                Business type
              </label>
              <select
                id="business_type"
                name="business_type"
                required
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"
              >
                <option value="">Select...</option>
                {businessTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="state"
                className="block text-sm font-medium mb-1"
              >
                State
              </label>
              <select
                id="state"
                name="state"
                required
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"
              >
                <option value="">Select...</option>
                {states.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div className="col-span-2">
              <label
                htmlFor="email"
                className="block text-sm font-medium mb-1"
              >
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"
                placeholder="you@example.com"
              />
            </div>

            <div className="col-span-2">
              <label
                htmlFor="suburb"
                className="block text-sm font-medium mb-1"
              >
                Suburb
              </label>
              <input
                id="suburb"
                name="suburb"
                type="text"
                required
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/30"
                placeholder="e.g. Bondi Junction"
              />
            </div>

            <fieldset className="col-span-2 mt-4">
              <legend className="block text-sm font-medium mb-2">
                Jobs you want
              </legend>
              <div className="space-y-2">
                {jobOptions.map((job) => (
                  <label
                    key={job.value}
                    className="flex items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      name="jobs"
                      value={job.value}
                      className="h-4 w-4 rounded border-border text-accent accent-accent"
                    />
                    {job.name}
                  </label>
                ))}
              </div>
            </fieldset>

            <button
              type="submit"
              disabled={submitting}
              className={`col-span-2 w-full rounded-lg py-3 font-semibold mt-6 transition-colors ${
                submitting
                  ? "bg-primary text-primary-foreground opacity-50 cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-accent hover:text-accent-foreground"
              }`}
            >
              {submitting ? "Starting trial..." : "Start free trial"}
            </button>
          </form>

          {error && (
            <p className="mt-4 text-sm text-destructive text-center">
              {error}
            </p>
          )}

          <div className="mt-6 pt-6 border-t border-border text-center">
            <p className="text-sm text-muted-foreground">
              Already have an account?{" "}
              <a href="/demo" className="text-accent font-medium hover:underline">
                Try the demo instead
              </a>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
