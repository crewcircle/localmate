"use client";

import { useState, useEffect } from "react";
import { Plus, ExternalLink, X } from "lucide-react";
import DemoBadge from "@/components/DemoBadge";
import { api } from "@/lib/api";
import { stubClients } from "@/lib/stubs";
import type { Client } from "@/lib/stubs";

const BUSINESS_TYPES = [
  "Dental",
  "Medical",
  "Legal",
  "Hospitality",
  "Retail",
  "Fitness",
  "Beauty",
];
const SUBURBS = [
  "Bondi Junction",
  "Surry Hills",
  "Parramatta",
  "Newtown",
  "Chatswood",
];
const STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];
const ALL_JOBS = [
  "Review Guard",
  "Rank Report",
  "Competitor Watch",
  "Rebook",
  "Menu Sync",
];

const trialStatusColors: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  expiring_soon: "bg-amber-100 text-amber-700",
  expired: "bg-red-100 text-red-700",
};

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    business_name: "",
    business_type: "",
    suburb: "",
    state: "NSW",
    jobs: [] as string[],
  });

  useEffect(() => {
    api
      .get<Client[]>("/clients")
      .then((data) => setClients(data ?? stubClients))
      .catch(() => setClients(stubClients));
  }, []);

  const handleAddClient = async () => {
    await api.post("/auth/signup", form);
    setShowModal(false);
    setForm({
      business_name: "",
      business_type: "",
      suburb: "",
      state: "NSW",
      jobs: [],
    });
  };

  const handleConnectGbp = async (clientId: string) => {
    const url = await api.get<{ url: string }>(
      `/auth/gbp-oauth-url?client_id=${clientId}`
    );
    if (url?.url) {
      window.open(url.url, "_blank");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Clients</h1>
          <p className="mt-1 text-sm text-gray-500">Manage your client roster</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> Add Client
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              <th className="px-4 py-3">Business</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Trial</th>
              <th className="px-4 py-3">Days Left</th>
              <th className="px-4 py-3">Active Jobs</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => {
              const daysLeft = Math.ceil(
                (new Date(client.trial_ends_at).getTime() - Date.now()) /
                  (1000 * 60 * 60 * 24)
              );
              return (
                <tr
                  key={client.id}
                  className="border-b last:border-0 hover:bg-gray-50"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {client.business_name}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {client.business_type}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        trialStatusColors[client.trial_status]
                      }`}
                    >
                      {client.trial_status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {Math.max(0, daysLeft)}d
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {client.active_jobs.map((job) => (
                        <span
                          key={job}
                          className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700"
                        >
                          {job}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleConnectGbp(client.id)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
                    >
                      <ExternalLink className="h-3 w-3" /> Connect GBP
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                Add Client
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Business Name
                </label>
                <input
                  type="text"
                  className="mt-1 w-full rounded border px-3 py-2 text-sm"
                  value={form.business_name}
                  onChange={(e) =>
                    setForm({ ...form, business_name: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Business Type
                </label>
                <select
                  className="mt-1 w-full rounded border px-3 py-2 text-sm"
                  value={form.business_type}
                  onChange={(e) =>
                    setForm({ ...form, business_type: e.target.value })
                  }
                >
                  <option value="">Select...</option>
                  {BUSINESS_TYPES.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Suburb
                  </label>
                  <select
                    className="mt-1 w-full rounded border px-3 py-2 text-sm"
                    value={form.suburb}
                    onChange={(e) =>
                      setForm({ ...form, suburb: e.target.value })
                    }
                  >
                    <option value="">Select...</option>
                    {SUBURBS.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    State
                  </label>
                  <select
                    className="mt-1 w-full rounded border px-3 py-2 text-sm"
                    value={form.state}
                    onChange={(e) =>
                      setForm({ ...form, state: e.target.value })
                    }
                  >
                    {STATES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Active Jobs
                </label>
                <div className="mt-1 flex flex-wrap gap-2">
                  {ALL_JOBS.map((job) => (
                    <label
                      key={job}
                      className="flex items-center gap-1 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={form.jobs.includes(job)}
                        onChange={(e) => {
                          setForm({
                            ...form,
                            jobs: e.target.checked
                              ? [...form.jobs, job]
                              : form.jobs.filter((j) => j !== job),
                          });
                        }}
                      />
                      {job}
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowModal(false)}
                className="rounded border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddClient}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                Add Client
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
