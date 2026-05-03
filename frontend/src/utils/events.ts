import type { EventType, EventStatus } from "@/types";

export const EVENT_TYPE_LABELS: Record<EventType, string> = {
  fire:       "שריפה",
  explosion:  "פיצוץ",
  shooting:   "ירי",
  accident:   "תאונה",
  flood:      "שיטפון",
  earthquake: "רעידת אדמה",
  protest:    "הפגנה",
  crime:      "פשע",
  terror:     "פיגוע",
  medical:    "רפואי",
  other:      "אחר",
  unknown:    "לא ידוע",
};

export const EVENT_TYPE_COLORS: Record<EventType, string> = {
  fire:       "#ef4444",
  explosion:  "#f97316",
  shooting:   "#dc2626",
  accident:   "#f59e0b",
  flood:      "#3b82f6",
  earthquake: "#8b5cf6",
  protest:    "#10b981",
  crime:      "#6b7280",
  terror:     "#991b1b",
  medical:    "#06b6d4",
  other:      "#9ca3af",
  unknown:    "#6b7280",
};

export const STATUS_LABELS: Record<EventStatus, string> = {
  new:       "חדש",
  updated:   "עודכן",
  verified:  "מאומת",
  duplicate: "כפול",
  archived:  "ארכיון",
};

export const STATUS_COLORS: Record<EventStatus, string> = {
  new:       "bg-blue-100 text-blue-800",
  updated:   "bg-yellow-100 text-yellow-800",
  verified:  "bg-green-100 text-green-800",
  duplicate: "bg-gray-100 text-gray-600",
  archived:  "bg-gray-100 text-gray-400",
};

export function formatDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("he-IL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function confidenceBar(confidence?: number): string {
  if (confidence == null) return "—";
  const pct = Math.round(confidence * 100);
  return `${pct}%`;
}
