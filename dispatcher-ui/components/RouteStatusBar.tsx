"use client";

import { format, parseISO } from "date-fns";
import type { TelemetryEventCurrent } from "@/lib/telemetryBackend";

function pct(n: number | null | undefined): number | null {
  if (n == null || Number.isNaN(n)) return null;
  return Math.max(0, Math.min(100, n));
}

function fmtKm(km: number | null | undefined): string {
  if (km == null || Number.isNaN(km)) return "—";
  return km < 10 ? `${km.toFixed(1)} км` : `${Math.round(km)} км`;
}

function fmtEta(iso: string | null | undefined): string {
  if (!iso?.trim()) return "—";
  try {
    const d = parseISO(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return format(d, "HH:mm");
  } catch {
    return "—";
  }
}

export function RouteStatusBar({
  event,
  routeTitle,
}: {
  event: TelemetryEventCurrent | null;
  routeTitle: string;
}) {
  const p = pct(event?.route_progress_percent ?? null);
  const w = p ?? 0;

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-slate-200 bg-slate-100 px-3 py-2.5">
        <div className="flex items-center gap-3">
          <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-300/80">
            <div
              className="h-full rounded-full bg-emerald-600 transition-[width] duration-500"
              style={{ width: p != null ? `${w}%` : "0%" }}
            />
          </div>
          <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-800">
            {p != null ? `${Math.round(p)}%` : "—"}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div className="rounded border border-slate-200 bg-white px-3 py-2">
          <p className="text-[10px] font-medium text-slate-500">До пункта назначения</p>
          <p className="text-base font-semibold tabular-nums text-slate-900">
            {fmtKm(event?.distance_to_destination_km)}
          </p>
        </div>
        <div className="rounded border border-slate-200 bg-white px-3 py-2">
          <p className="text-[10px] font-medium text-slate-500">Ожидаемое прибытие</p>
          <p className="text-base font-semibold tabular-nums text-slate-900">{fmtEta(event?.eta_timestamp)}</p>
        </div>
        <div className="rounded border border-slate-200 bg-white px-3 py-2">
          <p className="text-[10px] font-medium text-slate-500">Маршрут</p>
          <p className="text-base font-semibold leading-snug text-slate-900 break-words">{routeTitle}</p>
        </div>
      </div>
    </div>
  );
}
