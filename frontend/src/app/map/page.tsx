"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/utils/api";
import type { MapPoint, EventDetail } from "@/types";
import { EVENT_TYPE_LABELS, EVENT_TYPE_COLORS, formatDate } from "@/utils/events";

// Leaflet must be loaded client-side only
const MapView = dynamic(() => import("@/components/map/MapView"), { ssr: false });

// ── Event side panel ──────────────────────────────────────────────────────────
function EventPanel({ eventId, onClose }: { eventId: number; onClose: () => void }) {
  const [event, setEvent] = useState<EventDetail | null>(null);

  useEffect(() => {
    api.getEvent(eventId).then(setEvent);
  }, [eventId]);

  if (!event) return (
    <div className="w-80 radar-card p-4 flex items-center justify-center h-48">
      <div className="w-5 h-5 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const color = EVENT_TYPE_COLORS[event.event_type];

  return (
    <div className="w-80 radar-card overflow-hidden flex flex-col max-h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 flex-shrink-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-0.5" style={{ backgroundColor: color }} />
            <span className="text-xs text-gray-400">{EVENT_TYPE_LABELS[event.event_type]}</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-lg leading-none">×</button>
        </div>
        <h3 className="text-sm font-semibold text-white mt-2 leading-snug">
          {event.canonical_title || "ללא כותרת"}
        </h3>
      </div>

      {/* Body */}
      <div className="overflow-y-auto flex-1 p-4 space-y-3 text-sm">
        {event.summary && (
          <p className="text-gray-400 text-xs leading-relaxed">{event.summary}</p>
        )}

        <div className="grid grid-cols-2 gap-2">
          {event.location_text && (
            <div className="col-span-2">
              <p className="text-xs text-gray-600">מיקום</p>
              <p className="text-gray-300">{event.location_text}</p>
            </div>
          )}
          {event.event_time && (
            <div>
              <p className="text-xs text-gray-600">זמן אירוע</p>
              <p className="text-gray-300">{formatDate(event.event_time)}</p>
            </div>
          )}
          {event.injured_count != null && (
            <div>
              <p className="text-xs text-gray-600">פצועים</p>
              <p className="text-orange-400 font-medium">{event.injured_count}</p>
            </div>
          )}
          {event.killed_count != null && (
            <div>
              <p className="text-xs text-gray-600">הרוגים</p>
              <p className="text-red-400 font-medium">{event.killed_count}</p>
            </div>
          )}
        </div>

        {/* Confidence */}
        <div className="flex gap-3">
          {event.parser_confidence != null && (
            <div>
              <p className="text-xs text-gray-600">דיוק parser</p>
              <p className="text-xs text-gray-400">{Math.round(event.parser_confidence * 100)}%</p>
            </div>
          )}
          {event.geocode_confidence != null && (
            <div>
              <p className="text-xs text-gray-600">דיוק geo</p>
              <p className="text-xs text-gray-400">{Math.round(event.geocode_confidence * 100)}%</p>
            </div>
          )}
        </div>

        {/* Media */}
        {event.media.length > 0 && (
          <div>
            <p className="text-xs text-gray-600 mb-2">מדיה ({event.media.length})</p>
            <div className="space-y-1">
              {event.media.map((m) => (
                <a
                  key={m.id}
                  href={m.media_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 truncate"
                >
                  <span>{m.media_type === "video" ? "🎥" : "🖼️"}</span>
                  <span className="truncate">{m.caption || m.media_url}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Reports count */}
        <div className="pt-2 border-t border-gray-800">
          <p className="text-xs text-gray-500">
            {event.reports.length} דיווחים · עודכן {formatDate(event.last_seen_at)}
          </p>
          <a
            href={`/events/${event.id}`}
            className="text-xs text-red-400 hover:text-red-300 mt-1 block"
          >
            פרטים מלאים →
          </a>
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function MapPage() {
  const [points, setPoints]         = useState<MapPoint[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<string>("");
  const [loading, setLoading]       = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getMapPoints({ event_type: filterType || undefined })
      .then(setPoints)
      .finally(() => setLoading(false));
  }, [filterType]);

  const typeOptions = Object.entries(EVENT_TYPE_LABELS);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">מפת אירועים</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {loading ? "טוען..." : `${points.length} אירועים עם מיקום`}
          </p>
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="bg-gray-900 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-red-500"
        >
          <option value="">כל הסוגים</option>
          {typeOptions.map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Map + Panel */}
      <div className="flex gap-4 items-start">
        <div className="flex-1 radar-card overflow-hidden" style={{ height: "calc(100vh - 200px)", minHeight: 400 }}>
          {typeof window !== "undefined" && (
            <MapView
              points={points}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </div>

        {selectedId && (
          <EventPanel eventId={selectedId} onClose={() => setSelectedId(null)} />
        )}
      </div>
    </div>
  );
}
