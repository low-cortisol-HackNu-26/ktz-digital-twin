"use client";

import { useEffect, useMemo } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import {
  ROUTE_LINE,
  positionAlongRoute,
  useMockDashboardStore,
} from "@/store/mockDashboardStore";
import { formatSpeed } from "@/lib/utils";

function Recenter({ position }: { position: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.panTo(position);
  }, [map, position]);
  return null;
}

export default function RailwayMap() {
  const progress = useMockDashboardStore((s) => s.routeProgress);
  const packet = useMockDashboardStore((s) => s.packet);
  const pos = useMemo(() => positionAlongRoute(progress), [progress]);
  const center = pos;

  return (
    <section className="panel flex h-[min(640px,calc(100vh-220px))] flex-col">
      <div className="mb-4 shrink-0">
        <h2 className="text-sm font-medium text-slate-400">Route map</h2>
        <p className="mt-1 text-xs text-slate-500">
          Demo corridor with live position interpolated along the polyline (mock).
        </p>
        <p className="readout-sm mt-2 text-slate-400">
          {packet.locomotive_id} · {formatSpeed(packet.speed)}
        </p>
      </div>
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-lg border border-cabin-border">
        <MapContainer
          center={center}
          zoom={11}
          className="z-0 h-full w-full"
          scrollWheelZoom
        >
          <Recenter position={pos} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> · <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />
          <Polyline
            positions={ROUTE_LINE}
            pathOptions={{ color: "#38bdf8", weight: 4, opacity: 0.85 }}
          />
          <CircleMarker
            center={pos}
            radius={11}
            pathOptions={{
              color: "#f8fafc",
              weight: 2,
              fillColor: "#0ea5e9",
              fillOpacity: 0.95,
            }}
          >
            <Tooltip direction="top" offset={[0, -8]} opacity={1}>
              <span className="text-xs font-medium text-slate-900">
                {packet.locomotive_id}
              </span>
            </Tooltip>
            <Popup>
              <div className="text-slate-900">
                <p className="font-semibold">{packet.locomotive_id}</p>
                <p className="text-sm">{formatSpeed(packet.speed)}</p>
              </div>
            </Popup>
          </CircleMarker>
        </MapContainer>
      </div>
    </section>
  );
}
