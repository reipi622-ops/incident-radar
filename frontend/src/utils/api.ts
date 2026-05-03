import axios from "axios";
import type {
  Event, EventDetail, MapPoint, StatsSummary,
  PaginatedResponse, EventFilters,
} from "@/types";

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 10000,
});

export const api = {
  // Stats
  getStats: () =>
    API.get<StatsSummary>("/stats/summary").then((r) => r.data),

  // Events
  getEvents: (filters: Partial<EventFilters> = {}) =>
    API.get<PaginatedResponse<Event>>("/events", { params: filters }).then((r) => r.data),

  getEvent: (id: number) =>
    API.get<EventDetail>(`/events/${id}`).then((r) => r.data),

  getMapPoints: (params: { event_type?: string; date_from?: string; date_to?: string } = {}) =>
    API.get<MapPoint[]>("/events/map", { params }).then((r) => r.data),

  // Pipeline
  runAll: () =>
    API.post("/pipeline/run-all").then((r) => r.data),

  runCollect: () =>
    API.post("/pipeline/collect/run").then((r) => r.data),

  runParse: () =>
    API.post("/pipeline/parse/run").then((r) => r.data),

  runDedup: () =>
    API.post("/pipeline/dedup/run").then((r) => r.data),

  runGeocode: () =>
    API.post("/pipeline/geocode/run").then((r) => r.data),
};
