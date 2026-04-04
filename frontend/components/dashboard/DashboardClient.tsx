"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, BellRing, MapPinned, TrendingUp } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { useMockDashboardStore } from "@/store/mockDashboardStore";
import { MockTelemetryTicker } from "./MockTelemetryTicker";
import { HealthCheckView } from "@/components/health/HealthCheckView";
import { TrendAlertsView } from "@/components/alerts/TrendAlertsView";
import { TrendsView } from "@/components/trends/TrendsView";
import dynamic from "next/dynamic";

const RailwayMap = dynamic(() => import("@/components/map/RailwayMap"), {
  ssr: false,
  loading: () => (
    <section className="panel flex min-h-[480px] items-center justify-center text-slate-500">
      Loading map…
    </section>
  ),
});

const TAB_COUNT = 4;

const TAB_LABELS = [
  { label: "Health check", icon: Activity },
  { label: "Trend alerts", icon: BellRing },
  { label: "Trends", icon: TrendingUp },
  { label: "Map", icon: MapPinned },
] as const;

export function DashboardClient() {
  const [tab, setTab] = useState(0);
  const { driver } = useAuth();
  const connected = useMockDashboardStore((s) => s.connected);
  const latency = useMockDashboardStore((s) => s.simulatedLatencyMs);
  const receivedAt = useMockDashboardStore((s) => s.receivedAt);
  const loco = useMockDashboardStore((s) => s.packet.locomotive_id);

  const cycleTab = useCallback(() => {
    setTab((i) => (i + 1) % TAB_COUNT);
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      const t = e.target as HTMLElement | null;
      if (t?.closest?.('[data-kiosk-input="true"]')) return;
      e.preventDefault();
      cycleTab();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [cycleTab]);

  return (
    <div className="flex min-h-screen flex-col bg-cabin-bg text-slate-100 select-none">
      <MockTelemetryTicker />
      <header className="border-b border-cabin-border bg-cabin-panel/80 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
              KTZ digital twin
            </p>
            <h1 className="text-xl font-semibold text-white">
              Railway operations dashboard
            </h1>
            <p className="readout-sm mt-1">
              <span className="text-slate-200">{loco}</span>
              <span className="mx-2 text-slate-600">·</span>
              {driver ? (
                <>
                  {driver.name}
                  <span className="mx-2 text-slate-600">·</span>
                  {driver.role}
                  <span className="mx-2 text-slate-600">·</span>
                  ID {driver.company_id}
                </>
              ) : (
                "Operator"
              )}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div
              className={cn(
                "flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm",
                connected
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                  : "border-rose-500/40 bg-rose-500/10 text-rose-300",
              )}
            >
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  connected ? "animate-pulse bg-emerald-400" : "bg-rose-400",
                )}
              />
              {connected ? "Live (simulated)" : "No connection"}
            </div>
            {receivedAt ? (
              <span className="readout-sm text-slate-500">
                Last packet{" "}
                <span className="text-slate-300">
                  {format(new Date(receivedAt), "HH:mm:ss")}
                </span>
                <span className="mx-1.5 text-slate-600">·</span>~{latency}
                ms RTT (demo)
              </span>
            ) : null}
          </div>
        </div>

      </header>
    </div>
  );
}
