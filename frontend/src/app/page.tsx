"use client";

import { useEffect, useState } from "react";
import { api } from "@/utils/api";
import type { StatsSummary, Event } from "@/types";
import { EVENT_TYPE_LABELS, EVENT_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS, formatDate } from "@/utils/events";
import Link from "next/link";

// ── Stat Card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="radar-card p-5">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">{label}</p>
      <p className="text-3xl font-bold text-white tabular-nums">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

// ── Event Row ─────────────────────────────────────────────────────────────────
function EventRow({ event }: { event: Event }) {
  const color = EVENT_TYPE_COLORS[event.event_type];
  const statusClass = STATUS_COLORS[event.status];

  return (
    <Link href={`/events/${event.id}`}>
      <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-800/60 transition-colors cursor-pointer group">
        <div
          className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
          style={{ backgroundColor: color }}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-200 truncate group-hover:text-white transition-colors">
            {event.canonical_title || event.summary || "ללא כותרת"}
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-xs text-gray-500">{EVENT_TYPE_LABELS[event.event_type]}</span>
            {event.location_text && (
              <span className="text-xs text-gray-500">· {event.location_text}</span>
            )}
            {event.injured_count != null && (
              <span className="text-xs text-orange-400">· {event.injured_count} פצועים</span>
            )}
            {event.killed_count != null && (
              <span className="text-xs text-red-400">· {event.killed_count} הרוגים</span>
            )}
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded-full ${statusClass}`}>
            {STATUS_LABELS[event.status]}
          </span>
          <p className="text-xs text-gray-600 mt-1">{formatDate(event.last_seen_at)}</p>
        </div>
      </div>
    </Link>
  );
}

// ── Pipeline Button ───────────────────────────────────────────────────────────
function PipelineButton() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.runAll();
      setResult(`✓ ${res.details}`);
    } catch {
      setResult("שגיאה בהרצת pipeline");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={run}
        disabled={loading}
        className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors font-medium"
      >
        {loading ? "מריץ..." : "הרץ Pipeline"}
      </button>
      {result && <span className="text-xs text-gray-400">{result}</span>}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [stats, setStats]   = useState<StatsSummary | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getStats(),
      api.getEvents({ page: 1, page_size: 15 }),
    ]).then(([s, e]) => {
      setStats(s);
      setEvents(e.items);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm">טוען נתונים...</p>
        </div>
      </div>
    );
  }

  const topTypes = Object.entries(stats?.events_by_type || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">דשבורד</h1>
          <p className="text-sm text-gray-500 mt-0.5">סיכום אירועים ממקורות פומביים</p>
        </div>
        <PipelineButton />
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="אירועים"
          value={stats?.total_events ?? 0}
        />
        <StatCard
          label="דיווחים גולמיים"
          value={stats?.total_reports ?? 0}
        />
        <StatCard
          label="עם מיקום"
          value={stats?.events_with_location ?? 0}
          sub="על המפה"
        />
        <StatCard
          label="עם מדיה"
          value={stats?.events_with_media ?? 0}
          sub="תמונה / וידאו"
        />
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent events */}
        <div className="lg:col-span-2 radar-card">
          <div className="flex items-center justify-between p-4 border-b border-gray-800">
            <h2 className="font-semibold text-white text-sm">אירועים אחרונים</h2>
            <Link href="/events" className="text-xs text-red-400 hover:text-red-300 transition-colors">
              כל האירועים →
            </Link>
          </div>
          <div className="p-2">
            {events.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-8">
                אין אירועים עדיין. הרץ את ה-Pipeline כדי לטעון נתוני דמו.
              </p>
            ) : (
              events.map((e) => <EventRow key={e.id} event={e} />)
            )}
          </div>
        </div>

        {/* Sidebar — type breakdown */}
        <div className="space-y-4">
          <div className="radar-card p-4">
            <h2 className="font-semibold text-white text-sm mb-4">לפי סוג אירוע</h2>
            <div className="space-y-2">
              {topTypes.length === 0 ? (
                <p className="text-xs text-gray-500">אין נתונים</p>
              ) : topTypes.map(([type, count]) => {
                const total = stats?.total_events || 1;
                const pct = Math.round((count / total) * 100);
                const color = EVENT_TYPE_COLORS[type as keyof typeof EVENT_TYPE_COLORS] || "#6b7280";
                return (
                  <div key={type}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-400">{EVENT_TYPE_LABELS[type as keyof typeof EVENT_TYPE_LABELS] || type}</span>
                      <span className="text-gray-500 tabular-nums">{count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${pct}%`, backgroundColor: color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="radar-card p-4">
            <h2 className="font-semibold text-white text-sm mb-4">לפי סטטוס</h2>
            <div className="space-y-1.5">
              {Object.entries(stats?.events_by_status || {}).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[status as keyof typeof STATUS_COLORS] || "bg-gray-800 text-gray-400"}`}>
                    {STATUS_LABELS[status as keyof typeof STATUS_LABELS] || status}
                  </span>
                  <span className="text-sm font-medium text-gray-300 tabular-nums">{count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="radar-card p-4">
            <h2 className="font-semibold text-white text-sm mb-3">ניווט מהיר</h2>
            <div className="space-y-2">
              <Link href="/map" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
                <span>🗺️</span> מפת אירועים
              </Link>
              <Link href="/events" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
                <span>📋</span> טבלת אירועים
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
