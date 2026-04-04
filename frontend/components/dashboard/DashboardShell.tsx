"use client";

import { useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Activity, BellRing, MapPinned, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { shouldSuppressDashboardSpaceCycle } from "@/lib/kiosk";
import { useAuth } from "@/context/AuthContext";
import { useMockDashboardStore } from "@/store/mockDashboardStore";
import { MockTelemetryTicker } from "./MockTelemetryTicker";
import { format } from "date-fns";

/** Order: Health → Alerts → Trends → Map (Space cycles forward). */
export const DASHBOARD_TAB_PATHS = [
  "/dashboard/health",
  "/dashboard/alerts",
  "/dashboard/trends",
  "/dashboard/map",
] as const;

const TAB_META = [
  { label: "Health check", icon: Activity },
  { label: "Trend alerts", icon: BellRing },
  { label: "Trends", icon: TrendingUp },
  { label: "Map", icon: MapPinned },
] as const;

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { driver } = useAuth();
  const connected = useMockDashboardStore((s) => s.connected);
  const latency = useMockDashboardStore((s) => s.simulatedLatencyMs);
  const receivedAt = useMockDashboardStore((s) => s.receivedAt);
  const loco = useMockDashboardStore((s) => s.packet.locomotive_id);

  const activeIndex = DASHBOARD_TAB_PATHS.indexOf(
    pathname as (typeof DASHBOARD_TAB_PATHS)[number],
  );
  const resolvedIndex = activeIndex >= 0 ? activeIndex : 0;

  const cycleTab = useCallback(() => {
    const i = DASHBOARD_TAB_PATHS.indexOf(
      pathname as (typeof DASHBOARD_TAB_PATHS)[number],
    );
    const current = i >= 0 ? i : 0;
    const next = (current + 1) % DASHBOARD_TAB_PATHS.length;
    router.push(DASHBOARD_TAB_PATHS[next]);
  }, [pathname, router]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      if (shouldSuppressDashboardSpaceCycle(e.target)) return;
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
            <div className="flex items-center gap-2">
            <img src="/images/logo.png" alt="Logo" className="w-9 h-12" />
            <div className="flex flex-col">
            <h1 className="text-xl font-bold text-primary">
              КЖД
            </h1>
            <p className="text-sm text-gray-500">Система мониторинга локомотивов</p>
            </div>
            </div>
          </div>
          <div className="flex flex-col  gap-2 text-left">
          <h1 className="text-2xl font-bold text-primary">
              {driver?.name}
            </h1>
            <p className="text-sm text-gray-500">Машинист локомотива</p>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-6 py-6">{children}</main>
    </div>
  );
}
