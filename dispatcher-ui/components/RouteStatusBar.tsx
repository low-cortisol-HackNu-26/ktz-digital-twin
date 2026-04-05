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
      <div className="rounded-xl border border-sky-500/40 bg-slate-900/80 px-4 py-3">
        <div className="flex items-center gap-4">
          <div className="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-emerald-500 transition-[width] duration-500"
              style={{ width: p != null ? `${w}%` : "0%" }}
            />
          </div>
          <span className="shrink-0 text-lg font-bold tabular-nums text-white">
            {p != null ? `${Math.round(p)}%` : "—"}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200/80 bg-white px-3 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">
            До пункта назначения
          </p>
          <p className="text-lg font-bold text-slate-800">{fmtKm(event?.distance_to_destination_km)}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white px-3 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">
            Ожидаемое прибытие
          </p>
          <p className="text-lg font-bold text-slate-800">{fmtEta(event?.eta_timestamp)}</p>
        </div>
        <div className="rounded-xl border border-slate-200/80 bg-white px-3 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">Маршрут</p>
          <p className="text-lg font-bold leading-tight text-slate-800 break-words">{routeTitle}</p>
        </div>
      </div>
    </div>
  );
}
