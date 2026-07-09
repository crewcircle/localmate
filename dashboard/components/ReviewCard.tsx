"use client";

import { useState } from "react";
import { Star, Trash2, Check, Edit3, Clock } from "lucide-react";
import { differenceInHours, parseISO } from "date-fns";
import DemoBadge from "./DemoBadge";
import type { DraftReview } from "@/lib/stubs";

interface ReviewCardProps {
  review: DraftReview;
  onApprove?: (id: string) => void;
  onDiscard?: (id: string) => void;
}

export default function ReviewCard({
  review,
  onApprove,
  onDiscard,
}: ReviewCardProps) {
  const [editing, setEditing] = useState(false);
  const [editedText, setEditedText] = useState(review.draft);
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const slaHours = differenceInHours(new Date(), parseISO(review.created_at));
  const slaColor =
    slaHours < 24
      ? "text-green-600"
      : slaHours < 48
        ? "text-amber-600"
        : "text-red-600";

  const handleApprove = () => {
    onApprove?.(review.id);
    setDismissed(true);
  };

  const handleDiscard = () => {
    if (window.confirm("Discard this draft?")) {
      onDiscard?.(review.id);
      setDismissed(true);
    }
  };

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="flex">
              {[1, 2, 3, 4, 5].map((s) => (
                <Star
                  key={s}
                  className={`h-4 w-4 ${
                    s <= review.rating
                      ? "fill-amber-400 text-amber-400"
                      : "text-gray-300"
                  }`}
                />
              ))}
            </div>
            <span className="text-sm font-medium text-gray-900">
              {review.reviewer}
            </span>
            <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs uppercase text-gray-500">
              {review.source}
            </span>
          </div>
          <p className="text-sm text-gray-700">{review.review}</p>
          <div className={`flex items-center gap-1 text-xs ${slaColor}`}>
            <Clock className="h-3 w-3" />
            <span>SLA: {slaHours}h ago</span>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
            AI Draft
          </p>
          {editing ? (
            <textarea
              className="w-full rounded border p-2 text-sm"
              rows={4}
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
            />
          ) : (
            <p className="rounded bg-blue-50 p-2 text-sm text-gray-700">
              {review.draft}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleApprove}
              className="inline-flex items-center gap-1 rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
            >
              <Check className="h-3 w-3" /> Approve & Post
            </button>
            {editing ? (
              <button
                onClick={() => {
                  setEditing(false);
                  handleApprove();
                }}
                className="inline-flex items-center gap-1 rounded border px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <Check className="h-3 w-3" /> Save
              </button>
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1 rounded border px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                <Edit3 className="h-3 w-3" /> Edit & Post
              </button>
            )}
            <button
              onClick={handleDiscard}
              className="inline-flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-red-600"
            >
              <Trash2 className="h-3 w-3" /> Discard
            </button>
            <DemoBadge />
          </div>
        </div>
      </div>
    </div>
  );
}
