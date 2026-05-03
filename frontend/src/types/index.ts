export type EventType =
  | "fire" | "explosion" | "shooting" | "accident" | "flood"
  | "earthquake" | "protest" | "crime" | "terror" | "medical"
  | "other" | "unknown";

export type EventStatus = "new" | "updated" | "verified" | "duplicate" | "archived";

export type MediaType = "image" | "video" | "audio" | "document" | "unknown";

export interface EventMedia {
  id: number;
  media_type: MediaType;
  media_url: string;
  thumbnail_url?: string;
  source_url?: string;
  caption?: string;
}

export interface Event {
  id: number;
  canonical_title?: string;
  summary?: string;
  event_type: EventType;
  injured_count?: number;
  killed_count?: number;
  affected_people_text?: string;
  event_time?: string;
  reported_time?: string;
  location_text?: string;
  latitude?: number;
  longitude?: number;
  geocode_confidence?: number;
  parser_confidence?: number;
  status: EventStatus;
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
  media: EventMedia[];
}

export interface EventDetail extends Event {
  reports: {
    id: number;
    raw_report_id: number;
    relation_type: string;
    dedup_score?: number;
    dedup_reason?: string;
    created_at: string;
  }[];
  updates: {
    id: number;
    field_name: string;
    old_value?: string;
    new_value?: string;
    created_at: string;
  }[];
}

export interface MapPoint {
  id: number;
  canonical_title?: string;
  event_type: EventType;
  event_time?: string;
  location_text?: string;
  latitude: number;
  longitude: number;
  injured_count?: number;
  killed_count?: number;
  has_media: boolean;
}

export interface StatsSummary {
  total_events: number;
  total_reports: number;
  events_with_location: number;
  events_with_media: number;
  events_by_type: Record<string, number>;
  events_by_status: Record<string, number>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface EventFilters {
  event_type?: string;
  status?: string;
  location?: string;
  date_from?: string;
  date_to?: string;
  min_injured?: number;
  page: number;
  page_size: number;
}
