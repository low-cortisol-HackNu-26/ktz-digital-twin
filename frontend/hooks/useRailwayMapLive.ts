"use client";

import { useEffect, useState } from "react";
import {
  fetchMapRoutes,
  pickRoutePolyline,
  pickRoutePolylineByCode,
  type RouteCollection,
} from "@/lib/mapApi";
import {
  fetchLocomotiveCurrent,
  routeCodeFromSegment,
  type LocomotiveCurrentResponse,
} from "@/lib/telemetryApi";

const POLL_MS = 100;

export type RailwayMapLive = {
  routeLine: [number, number][] | null;
  marker: [number, number] | null;
  speedKph: number | null;
  lastTelemetry: LocomotiveCurrentResponse | null;
};

export function useRailwayMapLive(locomotiveId: string): RailwayMapLive {
  const [routes, setRoutes] = useState<RouteCollection | null>(null);
  const [live, setLive] = useState<RailwayMapLive>({
    routeLine: null,
    marker: null,
    speedKph: null,
    lastTelemetry: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function loadRoutesOnce() {
      const data = await fetchMapRoutes();
      if (!cancelled && data) setRoutes(data);
    }

    void loadRoutesOnce();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!locomotiveId) return;

    let cancelled = false;

    async function tick() {
      const current = await fetchLocomotiveCurrent(locomotiveId);
      if (cancelled) return;

      if (!current?.event) {
        setLive({
          routeLine: routes ? pickRoutePolyline(routes, null) : null,
          marker: null,
          speedKph: null,
          lastTelemetry: current,
        });
        return;
      }

      const ev = current.event;
      const code = routeCodeFromSegment(ev.route_segment);
      const line =
        routes != null
          ? pickRoutePolylineByCode(routes, code) ??
            pickRoutePolyline(routes, null)
          : null;

      let marker: [number, number] | null = null;
      if (ev.gps_lat != null && ev.gps_lon != null) {
        marker = [ev.gps_lat, ev.gps_lon];
      }

      setLive({
        routeLine: line,
        marker,
        speedKph: typeof ev.speed_kph === "number" ? ev.speed_kph : null,
        lastTelemetry: current,
      });
    }

    void tick();
    const id = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [locomotiveId, routes]);

  return live;
}
