"use client";

import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { LocoStatusInfo, RouteCollection } from "@/lib/dispatcherApi";
import { lngLatToLeafletPair } from "@/lib/dispatcherApi";

function FitFleet({
  positions,
  lines,
}: {
  positions: [number, number][];
  lines: [number, number][][];
}) {
  const map = useMap();
  useEffect(() => {
    const pts: L.LatLngExpression[] = [...positions];
    for (const line of lines) {
      for (const p of line) pts.push(p);
    }
    if (pts.length === 0) return;
    const b = L.latLngBounds(pts);
    map.fitBounds(b, { padding: [48, 48], maxZoom: 12, animate: false });
  }, [map, positions, lines]);
  return null;
}

function markerColor(l: LocoStatusInfo, selected: boolean): string {
  if (selected) return "#ef4444";
  if (l.active_critical_count > 0) return "#ef4444";
  if (l.active_noncritical_count > 0) return "#fbbf24";
  return "#22c55e";
}

export type FleetMapProps = {
  routes: RouteCollection | null;
  fleet: LocoStatusInfo[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

export default function FleetMap({ routes, fleet, selectedId, onSelect }: FleetMapProps) {
  const lines = useMemo(() => {
    if (!routes?.features?.length) return [] as [number, number][][];
    return routes.features
      .filter((f) => f.geometry?.coordinates?.length)
      .map((f) => lngLatToLeafletPair(f.geometry.coordinates));
  }, [routes]);

  const markers = useMemo(() => {
    return fleet.filter((l) => Number.isFinite(l.lat) && Number.isFinite(l.lng));
  }, [fleet]);

  const center: [number, number] = useMemo(() => {
    if (markers.length) {
      const s = markers.find((m) => m.locomotive_id === selectedId) ?? markers[0];
      return [s.lat, s.lng];
    }
    return [48.0, 66.9];
  }, [markers, selectedId]);

  const positionsForFit = markers.map((m) => [m.lat, m.lng] as [number, number]);

  return (
    <MapContainer
      center={center}
      zoom={8}
      className="z-0 h-full w-full"
      scrollWheelZoom
      attributionControl={false}
    >
      <FitFleet positions={positionsForFit} lines={lines} />
      <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
      {lines.map((positions, i) => (
        <Polyline
          key={i}
          positions={positions}
          pathOptions={{ color: "#4fb3e8", weight: 4, opacity: 0.88 }}
        />
      ))}
      {markers.map((l) => {
        const sel = l.locomotive_id === selectedId;
        const fill = markerColor(l, sel);
        return (
          <CircleMarker
            key={l.locomotive_id}
            center={[l.lat, l.lng]}
            radius={sel ? 14 : 9}
            pathOptions={{
              color: sel ? "#fefce8" : "#0f172a",
              weight: sel ? 3 : 2,
              fillColor: fill,
              fillOpacity: l.is_online ? 0.95 : 0.45,
            }}
            eventHandlers={{
              click: () => onSelect(l.locomotive_id),
            }}
          />
        );
      })}
    </MapContainer>
  );
}
