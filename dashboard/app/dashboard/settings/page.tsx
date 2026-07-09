"use client";

import { useState } from "react";
import { Save, X } from "lucide-react";
import DemoBadge from "@/components/DemoBadge";

const JOBS = [
  "Review Guard",
  "Rank Report",
  "Competitor Watch",
  "Rebook",
  "Menu Sync",
];

export default function SettingsPage() {
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
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your automation preferences
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-lg border bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">Active Jobs</h2>
          <p className="mb-4 text-sm text-gray-500">
            Toggle automations on/off
          </p>
          <div className="space-y-3">
            {JOBS.map((job) => (
              <label
                key={job}
                className="flex items-center justify-between"
              >
                <span className="text-sm font-medium text-gray-700">
                  {job}
                </span>
                <button
                  onClick={() =>
                    setJobToggles({ ...jobToggles, [job]: !jobToggles[job] })
                  }
                  className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${
                    jobToggles[job] ? "bg-blue-600" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      jobToggles[job]
                        ? "translate-x-4"
                        : "translate-x-0.5"
                    }`}
                    style={{ marginTop: "2px" }}
                  />
                </button>
              </label>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Voice Sample
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Used for AI-generated phone scripts
          </p>
          <textarea
            className="w-full rounded border p-3 text-sm"
            rows={5}
            value={voiceSample}
            onChange={(e) => setVoiceSample(e.target.value)}
          />
        </div>

        <div className="rounded-lg border bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">
            SEO Keywords
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Keywords to track in rankings
          </p>
          <div className="mb-3 flex gap-2">
            <input
              type="text"
              className="flex-1 rounded border px-3 py-1.5 text-sm"
              placeholder="Add keyword..."
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addKeyword()}
            />
            <button
              onClick={addKeyword}
              className="rounded bg-gray-100 px-3 py-1.5 text-sm font-medium hover:bg-gray-200"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((kw) => (
              <span
                key={kw}
                className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
              >
                {kw}
                <button
                  onClick={() => removeKeyword(kw)}
                  className="text-blue-400 hover:text-blue-600"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-lg border bg-white p-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Competitor URLs
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Sites to monitor for changes
          </p>
          <div className="mb-3 flex gap-2">
            <input
              type="text"
              className="flex-1 rounded border px-3 py-1.5 text-sm"
              placeholder="https://..."
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addUrl()}
            />
            <button
              onClick={addUrl}
              className="rounded bg-gray-100 px-3 py-1.5 text-sm font-medium hover:bg-gray-200"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {competitorUrls.map((url) => (
              <span
                key={url}
                className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700"
              >
                {url.replace("https://", "")}
                <button
                  onClick={() => removeUrl(url)}
                  className="text-amber-400 hover:text-amber-600"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button className="inline-flex items-center gap-1 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Save className="h-4 w-4" /> Save Settings
        </button>
        <DemoBadge />
      </div>
    </div>
  );
}
