"use client";

import { format, parseISO } from "date-fns";
import type { TelemetryEventCurrent } from "@/lib/telemetryApi";

function clampPct(n: number | null | undefined): number | null {
  if (n == null || Number.isNaN(n)) return null;
  return Math.max(0, Math.min(100, n));
}

function formatDistanceKm(km: number | null | undefined): string {
  if (km == null || Number.isNaN(km)) return "—";
  if (km < 10) return `${km.toFixed(1)} км`;
  return `${Math.round(km)} км`;
}

function formatEtaLocal(iso: string | null | undefined): string {
  if (!iso?.trim()) return "—";
  try {
    const d = parseISO(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return format(d, "HH:mm");
  } catch {
    return "—";
  }
}

function routeSegmentFallback(routeSegment: string | null | undefined): string | null {
  if (!routeSegment?.trim()) return null;
  const code = routeSegment.split(":")[0]?.trim();
  return code ? code.toUpperCase() : null;
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200/90 bg-white px-4 py-3 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 break-words text-xl font-bold leading-tight text-slate-800">{value}</p>
    </div>
  );
}

export type MapRouteStatusPanelsProps = {
  event: TelemetryEventCurrent | null;
  routeDisplayName: string | null;
};

/**
 * Progress, remaining distance, ETA, and route title — data from GET …/current
 * and route name from GET /api/map/routes (no mock values).
 */
export function MapRouteStatusPanels({ event, routeDisplayName }: MapRouteStatusPanelsProps) {
  const pct = clampPct(event?.route_progress_percent ?? null);
  const pctWidth = pct ?? 0;
  const pctLabel = pct != null ? `${Math.round(pct)}%` : "—";

  const distanceLabel = formatDistanceKm(event?.distance_to_destination_km ?? null);
  const etaLabel = formatEtaLocal(event?.eta_timestamp ?? null);

  const routeLabel =
    routeDisplayName?.trim() ||
    routeSegmentFallback(event?.route_segment ?? null) ||
    "—";

  return (
    <div className="mt-4 shrink-0 space-y-3 bottom-0">
      <div className="rounded-lg bg-slate-100/40 px-4 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <div className="h-4 min-w-0 flex-1 overflow-hidden rounded-full bg-white">
            <div
              className="h-full rounded-full bg-emerald-500 transition-[width] duration-500 ease-out"
              style={{ width: pct != null ? `${pctWidth}%` : "0%" }}
              role="progressbar"
              aria-valuenow={pct ?? undefined}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Прогресс по маршруту"
            />
          </div>
          <span className="shrink-0 text-2xl font-bold tabular-nums text-white">{pctLabel}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 bg-slate-100/40 p-4 rounded-lg">
        <StatCard label="До пункта назначения" value={distanceLabel} />
        <StatCard label="Ожидаемое прибытие" value={etaLabel} />
        <StatCard label="Маршрут" value={routeLabel} />
      </div>
    </div>
  );
}
