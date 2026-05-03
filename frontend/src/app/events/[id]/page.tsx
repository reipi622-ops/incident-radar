"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { api } from "@/utils/api";
import type { EventDetail } from "@/types";
import { EVENT_TYPE_LABELS, EVENT_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS, formatDate } from "@/utils/events";

// Leaflet must be client-only
const MiniMap = dynamic(() => import("@/components/map/MiniMap"), { ssr: false });

function ConfidenceBadge({ value, label }: { value?: number; label: string }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "text-green-400" : pct >= 40 ? "text-yellow-400" : "text-red-400";
  return (
    <span className={`text-xs ${color}`}>
      {label}: {pct}%
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="radar-card">
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.getEvent(Number(id))
      .then(setEvent)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="text-center py-16 text-gray-500">
        <p>האירוע לא נמצא.</p>
        <Link href="/events" className="text-red-400 text-sm mt-2 inline-block hover:text-red-300">
          ← חזרה לרשימה
        </Link>
      </div>
    );
  }

  const typeColor = EVENT_TYPE_COLORS[event.event_type];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Back */}
      <Link href="/events" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
        ← כל האירועים
      </Link>

      {/* Header card */}
      <div className="radar-card p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span
                className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ backgroundColor: typeColor + "22", color: typeColor }}
              >
                {EVENT_TYPE_LABELS[event.event_type]}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[event.status]}`}>
                {STATUS_LABELS[event.status]}
              </span>
            </div>
            <h1 className="text-lg font-bold text-white leading-snug">
              {event.canonical_title || event.summary || "ללא כותרת"}
            </h1>
            {event.summary && event.canonical_title && (
              <p className="text-sm text-gray-400 mt-1">{event.summary}</p>
            )}
          </div>
        </div>

        {/* Key facts */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          {event.location_text && (
            <div className="bg-gray-800/50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-0.5">מיקום</p>
              <p className="text-sm text-gray-200">{event.location_text}</p>
            </div>
          )}
          {event.event_time && (
            <div className="bg-gray-800/50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-0.5">זמן אירוע</p>
              <p className="text-sm text-gray-200">{formatDate(event.event_time)}</p>
            </div>
          )}
          {event.injured_count != null && (
            <div className="bg-orange-900/20 border border-orange-800/30 rounded-lg p-3">
              <p className="text-xs text-orange-500 mb-0.5">פצועים</p>
              <p className="text-2xl font-bold text-orange-400">{event.injured_count}</p>
            </div>
          )}
          {event.killed_count != null && (
            <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-3">
              <p className="text-xs text-red-500 mb-0.5">הרוגים</p>
              <p className="text-2xl font-bold text-red-400">{event.killed_count}</p>
            </div>
          )}
        </div>

        {/* Confidence row */}
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-800">
          <ConfidenceBadge value={event.parser_confidence} label="חילוץ" />
          <ConfidenceBadge value={event.geocode_confidence} label="גיאוקוד" />
          <span className="text-xs text-gray-600 mr-auto">
            נראה לראשונה: {formatDate(event.first_seen_at)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Mini map */}
        {event.latitude && event.longitude && (
          <Section title="מיקום על המפה">
            <div className="h-48 rounded-lg overflow-hidden">
              <MiniMap lat={event.latitude} lng={event.longitude} title={event.canonical_title} />
            </div>
          </Section>
        )}

        {/* Media */}
        {event.media.length > 0 && (
          <Section title={`מדיה (${event.media.length})`}>
            <div className="space-y-2">
              {event.media.map((m) => (
                <a
                  key={m.id}
                  href={m.media_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-800 transition-colors group"
                >
                  <span className="text-lg">{m.media_type === "video" ? "🎥" : "🖼️"}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-300 truncate group-hover:text-white">
                      {m.caption || m.media_url.split("/").pop()}
                    </p>
                    <p className="text-xs text-gray-600">{m.media_type}</p>
                  </div>
                  <span className="text-xs text-gray-600 group-hover:text-red-400">↗</span>
                </a>
              ))}
            </div>
          </Section>
        )}
      </div>

      {/* Update timeline */}
      {event.updates.length > 0 && (
        <Section title={`היסטוריית עדכונים (${event.updates.length})`}>
          <div className="space-y-2">
            {event.updates.map((u) => (
              <div key={u.id} className="flex items-start gap-3 text-sm">
                <span className="text-gray-600 text-xs pt-0.5 tabular-nums flex-shrink-0">
                  {formatDate(u.created_at)}
                </span>
                <div className="flex-1">
                  <span className="text-gray-400">{u.field_name}: </span>
                  {u.old_value && (
                    <span className="line-through text-gray-600 mr-1">{u.old_value}</span>
                  )}
                  <span className="text-green-400">{u.new_value}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Linked reports */}
      {event.reports.length > 0 && (
        <Section title={`דיווחים משויכים (${event.reports.length})`}>
          <div className="space-y-2">
            {event.reports.map((r) => (
              <div key={r.id} className="flex items-center justify-between p-2 rounded-lg bg-gray-800/40 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">#{r.raw_report_id}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    r.relation_type === "primary" ? "bg-blue-900/50 text-blue-400" :
                    r.relation_type === "update"  ? "bg-green-900/50 text-green-400" :
                    r.relation_type === "duplicate" ? "bg-gray-800 text-gray-500" :
                    "bg-gray-800 text-gray-400"
                  }`}>
                    {r.relation_type}
                  </span>
                </div>
                {r.dedup_score != null && (
                  <span className="text-xs text-gray-500">
                    score: {Math.round(r.dedup_score * 100)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
