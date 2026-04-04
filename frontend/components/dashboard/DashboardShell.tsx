"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BellRing, MapPinned, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useMockDashboardStore } from "@/store/mockDashboardStore";
import { MockTelemetryTicker } from "./MockTelemetryTicker";
import { format } from "date-fns";

const tabs = [
  { href: "/dashboard/health", label: "Health check", icon: Activity },
  { href: "/dashboard/map", label: "Map", icon: MapPinned },
  { href: "/dashboard/trends", label: "Trends", icon: TrendingUp },
  { href: "/dashboard/alerts", label: "Trend alerts", icon: BellRing },
] as const;

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const connected = useMockDashboardStore((s) => s.connected);
  const latency = useMockDashboardStore((s) => s.simulatedLatencyMs);
  const receivedAt = useMockDashboardStore((s) => s.receivedAt);
  const loco = useMockDashboardStore((s) => s.packet.locomotive_id);

  return (
    <div className="flex min-h-screen flex-col bg-cabin-bg text-slate-100">
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
              Locomotive <span className="text-slate-200">{loco}</span>
              <span className="mx-2 text-slate-600">·</span>
              Auth off — mock telemetry only
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
        <nav
          className="mx-auto mt-4 flex max-w-[1600px] flex-wrap gap-2"
          aria-label="Dashboard sections"
        >
          {tabs.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors",
                  active
                    ? "border-sky-500/50 bg-sky-500/15 text-sky-100"
                    : "border-transparent bg-cabin-bg/60 text-slate-400 hover:border-cabin-border hover:text-slate-200",
                )}
              >
                <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-6 py-6">
        {children}
      </main>
    </div>
  );
}
