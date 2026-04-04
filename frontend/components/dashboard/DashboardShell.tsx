"use client";

import { useDashboardSpaceCycle } from "@/lib/dashboardTabCycle";
import { useAuth } from "@/context/AuthContext";
import { MockTelemetryTicker } from "./MockTelemetryTicker";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  useDashboardSpaceCycle();
  const { driver } = useAuth();

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
