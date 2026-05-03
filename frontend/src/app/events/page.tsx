"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/utils/api";
import type { Event, EventFilters } from "@/types";
import { EVENT_TYPE_LABELS, EVENT_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS, formatDate } from "@/utils/events";
import Link from "next/link";

const PAGE_SIZE = 20;

// ── Filter bar ────────────────────────────────────────────────────────────────
function FilterBar({
  filters,
  onChange,
}: {
  filters: Partial<EventFilters>;
  onChange: (f: Partial<EventFilters>) => void;
}) {
  return (
    <div className="radar-card p-4 flex flex-wrap gap-3 items-end">
      {/* Search by location */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">מיקום</label>
        <input
          type="text"
          placeholder="תל אביב..."
          value={filters.location || ""}
          onChange={(e) => onChange({ ...filters, location: e.target.value, page: 1 })}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 w-44 focus:outline-none focus:border-red-500"
        />
      </div>

      {/* Event type */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">סוג אירוע</label>
        <select
          value={filters.event_type || ""}
          onChange={(e) => onChange({ ...filters, event_type: e.target.value || undefined, page: 1 })}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-red-500"
        >
          <option value="">הכל</option>
          {Object.entries(EVENT_TYPE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Status */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">סטטוס</label>
        <select
          value={filters.status || ""}
          onChange={(e) => onChange({ ...filters, status: e.target.value || undefined, page: 1 })}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-red-500"
        >
          <option value="">הכל</option>
          {Object.entries(STATUS_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
      </div>

      {/* Min injured */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">פצועים מינימום</label>
        <input
          type="number"
          min={0}
          placeholder="0"
          value={filters.min_injured ?? ""}
          onChange={(e) =>
            onChange({ ...filters, min_injured: e.target.value ? Number(e.target.value) : undefined, page: 1 })
          }
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 w-28 focus:outline-none focus:border-red-500"
        />
      </div>

      {/* Date from */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-gray-500">מתאריך</label>
        <input
          type="date"
          value={filters.date_from?.split("T")[0] || ""}
          onChange={(e) => onChange({ ...filters, date_from: e.target.value || undefined, page: 1 })}
          className="bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-red-500"
        />
      </div>

      {/* Reset */}
      <button
        onClick={() => onChange({ page: 1, page_size: PAGE_SIZE })}
        className="px-3 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg hover:border-gray-500 transition-colors"
      >
        נקה
      </button>
    </div>
  );
}

// ── Table row ─────────────────────────────────────────────────────────────────
function EventTableRow({ event }: { event: Event }) {
  const color      = EVENT_TYPE_COLORS[event.event_type];
  const statusClass = STATUS_COLORS[event.status];

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/40 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
          <span className="text-xs text-gray-400">{EVENT_TYPE_LABELS[event.event_type]}</span>
        </div>
      </td>
      <td className="px-4 py-3 max-w-xs">
        <Link href={`/events/${event.id}`} className="text-sm text-gray-200 hover:text-white transition-colors line-clamp-2">
          {event.canonical_title || event.summary || "ללא כותרת"}
        </Link>
      </td>
      <td className="px-4 py-3 text-sm text-gray-400">{event.location_text || "—"}</td>
      <td className="px-4 py-3 text-center">
        {event.injured_count != null
          ? <span className="text-orange-400 font-medium text-sm">{event.injured_count}</span>
          : <span className="text-gray-600">—</span>}
      </td>
      <td className="px-4 py-3 text-center">
        {event.killed_count != null
          ? <span className="text-red-400 font-medium text-sm">{event.killed_count}</span>
          : <span className="text-gray-600">—</span>}
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusClass}`}>
          {STATUS_LABELS[event.status]}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
        {formatDate(event.last_seen_at)}
      </td>
      <td className="px-4 py-3">
        {event.media.length > 0 && <span className="text-xs text-blue-400">📷</span>}
        {event.latitude && <span className="text-xs text-green-500 mr-1">📍</span>}
      </td>
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function EventsPage() {
  const [events, setEvents]   = useState<Event[]>([]);
  const [total, setTotal]     = useState(0);
  const [pages, setPages]     = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<Partial<EventFilters>>({ page: 1, page_size: PAGE_SIZE });

  const fetchEvents = useCallback(() => {
    setLoading(true);
    api.getEvents(filters)
      .then((res) => {
        setEvents(res.items);
        setTotal(res.total);
        setPages(res.pages);
      })
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  const page = filters.page || 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">אירועים</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {loading ? "טוען..." : `${total} תוצאות`}
          </p>
        </div>
      </div>

      <FilterBar filters={filters} onChange={setFilters} />

      <div className="radar-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right">
            <thead>
              <tr className="border-b border-gray-800">
                {["סוג", "כותרת", "מיקום", "פצועים", "הרוגים", "סטטוס", "עדכון אחרון", ""].map((h) => (
                  <th key={h} className="px-4 py-3 text-xs text-gray-500 font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500 text-sm">
                    <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                    טוען...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500 text-sm">
                    לא נמצאו אירועים. נסה לשנות את הפילטרים.
                  </td>
                </tr>
              ) : (
                events.map((e) => <EventTableRow key={e.id} event={e} />)
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <p className="text-xs text-gray-500">
              עמוד {page} מתוך {pages}
            </p>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) - 1 }))}
                className="px-3 py-1 text-xs rounded border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 disabled:opacity-30 transition-colors"
              >
                הקודם
              </button>
              <button
                disabled={page >= pages}
                onClick={() => setFilters((f) => ({ ...f, page: (f.page || 1) + 1 }))}
                className="px-3 py-1 text-xs rounded border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 disabled:opacity-30 transition-colors"
              >
                הבא
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
