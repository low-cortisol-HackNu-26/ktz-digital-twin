"use client";

import { useEffect, useMemo } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useRailwayMapLive } from "@/hooks/useRailwayMapLive";
import {
  ROUTE_LINE,
  positionAlongRoute,
  useMockDashboardStore,
} from "@/store/mockDashboardStore";
import { DEFAULT_TELEMETRY_LOCOMOTIVE_ID } from "@/lib/telemetryApi";
import { formatSpeed } from "@/lib/utils";
import { MapRouteStatusPanels } from "@/components/map/MapRouteStatusPanels";

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
  const mockPos = useMemo(() => positionAlongRoute(progress), [progress]);
  const locoId =
    process.env.NEXT_PUBLIC_MAP_LOCOMOTIVE_ID?.trim() ||
    DEFAULT_TELEMETRY_LOCOMOTIVE_ID;
  const live = useRailwayMapLive(locoId);
  const linePositions = live.routeLine ?? ROUTE_LINE;
  const pos = live.marker ?? mockPos;
  const center = pos;
  const speedLabel =
    live.speedKph != null ? formatSpeed(live.speedKph) : formatSpeed(packet.speed);

  return (
    <section className=" flex h-[min(720px,calc(100vh-180px))] flex-col">
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-lg border border-cabin-border pointer-events-none">
        <MapContainer
          center={center}
          zoom={12}
          className="z-0 h-full w-full"
          scrollWheelZoom={false}
          dragging={false}
          doubleClickZoom={false}
          boxZoom={false}
          keyboard={false}
          zoomControl={true}
          attributionControl={false}
        >
          <Recenter position={pos} />
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <Polyline
            positions={linePositions}
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
          />
        </MapContainer>
      </div>

      <MapRouteStatusPanels
        event={live.lastTelemetry?.event ?? null}
        routeDisplayName={live.routeDisplayName}
      />
    </section>
  );
}
