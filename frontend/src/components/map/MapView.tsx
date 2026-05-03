"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import type { MapPoint } from "@/types";
import { EVENT_TYPE_COLORS, EVENT_TYPE_LABELS } from "@/utils/events";

interface MapViewProps {
  points: MapPoint[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

const ISRAEL_CENTER: [number, number] = [31.5, 34.8];

function makeIcon(color: string, selected: boolean) {
  const size = selected ? 16 : 12;
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      <circle cx="${size / 2}" cy="${size / 2}" r="${size / 2 - 1}"
        fill="${color}" stroke="white" stroke-width="${selected ? 2 : 1.5}" opacity="0.9"/>
    </svg>
  `.trim();

  return L.divIcon({
    className: "",
    html: svg,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export default function MapView({ points, selectedId, onSelect }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef       = useRef<L.Map | null>(null);
  const layerRef     = useRef<L.LayerGroup | null>(null);

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: ISRAEL_CENTER,
      zoom: 8,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Re-render markers when points or selection changes
  useEffect(() => {
    if (!layerRef.current) return;
    layerRef.current.clearLayers();

    points.forEach((p) => {
      const color    = EVENT_TYPE_COLORS[p.event_type] || "#6b7280";
      const selected = p.id === selectedId;
      const icon     = makeIcon(color, selected);

      const lines: string[] = [
        `<b>${EVENT_TYPE_LABELS[p.event_type]}</b>`,
        p.canonical_title || "",
        p.location_text ? `📍 ${p.location_text}` : "",
        p.injured_count != null ? `🟠 ${p.injured_count} פצועים` : "",
        p.killed_count  != null ? `🔴 ${p.killed_count} הרוגים`  : "",
        p.has_media ? "📷 יש מדיה" : "",
      ].filter(Boolean);

      const marker = L.marker([p.latitude, p.longitude], { icon })
        .bindTooltip(lines.join("<br>"), { direction: "top", className: "radar-tooltip" })
        .on("click", () => onSelect(p.id));

      layerRef.current!.addLayer(marker);
    });
  }, [points, selectedId, onSelect]);

  // Pan to selected point
  useEffect(() => {
    if (!mapRef.current || !selectedId) return;
    const point = points.find((p) => p.id === selectedId);
    if (point) {
      mapRef.current.panTo([point.latitude, point.longitude], { animate: true });
    }
  }, [selectedId, points]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
