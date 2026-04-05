"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Download,
  Gauge,
  LogOut,
} from "lucide-react";
import {
  fetchBackendCurrent,
  type LocomotiveCurrentResponse,
} from "@/lib/telemetryBackend";
import {
  download15MinReportPdf,
  fetchDispatcherFleet,
  fetchDispatcherMapRoutes,
  fetchLocomotiveDetails,
  fleetLocoSubtitle,
  type FleetStatusResponse,
  type LocoDetailsWarning,
  type LocomotiveDetailsResponse,
  type RouteCollection,
} from "@/lib/dispatcherApi";
import {
  logoutDispatcher,
  readStoredSession,
  type StoredSession,
} from "@/lib/dispatcherAuth";
import { cn } from "@/lib/utils";
import { RouteStatusBar } from "@/components/RouteStatusBar";

const FleetMap = dynamic(() => import("@/components/FleetMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full min-h-[280px] items-center justify-center bg-[#0f1419] text-sm text-slate-500">
      Карта…
    </div>
  ),
});

const TOAST_MS = 5000;

function healthCategory(score: number | null | undefined): "Критично" | "Внимание" | "Норма" {
  if (score == null || Number.isNaN(score)) return "Норма";
  if (score < 45) return "Критично";
  if (score < 72) return "Внимание";
  return "Норма";
}

type ToastItem = { key: string; title: string; severity: string };

export function DispatcherApp() {
  const router = useRouter();
  const [session, setSession] = useState<StoredSession | null>(null);
  const [fleet, setFleet] = useState<FleetStatusResponse | null>(null);
  const [routes, setRoutes] = useState<RouteCollection | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [current, setCurrent] = useState<LocomotiveCurrentResponse | null>(null);
  const [details, setDetails] = useState<LocomotiveDetailsResponse | null>(null);
  const [expanded, setExpanded] = useState(true);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportErr, setReportErr] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastTimers = useRef<number[]>([]);
  const knownWarnRef = useRef<Set<string>>(new Set());
  const warnSeededRef = useRef(false);

  useEffect(() => {
    setSession(readStoredSession());
  }, []);

  useEffect(() => {
    if (!readStoredSession()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    async function tick() {
      const [f, r] = await Promise.all([fetchDispatcherFleet(), fetchDispatcherMapRoutes()]);
      if (cancelled) return;
      setFleet(f);
      setRoutes(r);
    }
    void tick();
    const id = window.setInterval(() => void tick(), 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [session]);

  useEffect(() => {
    if (!fleet?.locomotives?.length) return;
    setSelectedId((prev) => {
      if (prev && fleet.locomotives.some((l) => l.locomotive_id === prev)) return prev;
      const online = fleet.locomotives.find((l) => l.is_online);
      return (online ?? fleet.locomotives[0]).locomotive_id;
    });
  }, [fleet]);

  useEffect(() => {
    knownWarnRef.current = new Set();
    warnSeededRef.current = false;
    setReportErr(null);
  }, [selectedId]);

  const pushToast = useCallback((w: LocoDetailsWarning) => {
    const key = `${w.warning_id}-${Date.now()}`;
    setToasts((t) => [...t, { key, title: w.title, severity: w.severity }]);
    const tid = window.setTimeout(() => {
      setToasts((t) => t.filter((x) => x.key !== key));
      toastTimers.current = toastTimers.current.filter((x) => x !== tid);
    }, TOAST_MS);
    toastTimers.current.push(tid as unknown as number);
  }, []);

  useEffect(() => {
    return () => toastTimers.current.forEach(clearTimeout);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const locoId = selectedId;
    let cancelled = false;
    async function tick() {
      const [cur, det] = await Promise.all([
        fetchBackendCurrent(locoId),
        fetchLocomotiveDetails(locoId),
      ]);
      if (cancelled) return;
      setCurrent(cur);
      setDetails(det);

      const warnings = det?.warnings ?? [];
      if (!warnSeededRef.current) {
        knownWarnRef.current = new Set(warnings.map((w) => w.warning_id));
        warnSeededRef.current = true;
      } else {
        for (const w of warnings) {
          if (!knownWarnRef.current.has(w.warning_id)) pushToast(w);
        }
        knownWarnRef.current = new Set(warnings.map((w) => w.warning_id));
      }
    }
    void tick();
    const id = window.setInterval(() => void tick(), 3500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [selectedId, pushToast]);

  const selectedFleet = useMemo(
    () => fleet?.locomotives.find((l) => l.locomotive_id === selectedId) ?? null,
    [fleet, selectedId],
  );

  const ev = current?.event ?? null;
  const healthScore = current?.health_index?.overall_health_index ?? null;
  const hCat = healthCategory(healthScore);
  const electric = (ev?.traction_type ?? "electric") !== "diesel" && ev?.traction_type !== "fuel";

  const routeTitle = selectedFleet
    ? fleetLocoSubtitle(selectedFleet, routes)
    : ev?.route_segment?.split(":")[0]?.toUpperCase() || "—";

  const criticalN = selectedFleet?.active_critical_count ?? 0;
  const otherN = selectedFleet?.active_noncritical_count ?? 0;

  async function onLogout() {
    await logoutDispatcher();
    router.replace("/login");
  }

  async function onExportReport() {
    if (!selectedId) return;
    setReportErr(null);
    setReportBusy(true);
    const result = await download15MinReportPdf(selectedId);
    setReportBusy(false);
    if (!result.ok) setReportErr(result.message);
  }

  const metrics = useMemo(() => {
    if (!ev) return [];
    const temp = ev.engine_temperature_c ?? ev.traction_motor_temp_c ?? null;
    const voltV =
      ev.catenary_voltage_kv != null ? Math.round(ev.catenary_voltage_kv * 1000) : null;
    const curr = ev.traction_current_a ?? ev.current_a ?? null;
    const power = ev.traction_power_kw ?? null;
    const fuelOrEnergy = electric
      ? (ev.energy_consumption_kwh != null ? `${ev.energy_consumption_kwh.toFixed(1)} кВт·ч` : "—")
      : ev.fuel_level_percent != null
        ? `${Math.round(ev.fuel_level_percent)} %`
        : "—";
    return [
      {
        label: "Скорость",
        value: `${Math.round(ev.speed_kph)} км/ч`,
        left: "border-l-sky-500",
        text: "text-sky-700",
      },
      {
        label: electric ? "Энергия" : "Топливо",
        value: fuelOrEnergy,
        left: "border-l-amber-500",
        text: "text-amber-800",
      },
      {
        label: "Температура",
        value: temp != null ? `${temp.toFixed(0)} °C` : "—",
        left: "border-l-red-500",
        text: "text-red-700",
      },
      {
        label: "Мощность",
        value: power != null ? `${Math.round(power)} кВт` : "—",
        left: "border-l-emerald-500",
        text: "text-emerald-800",
      },
      {
        label: "Напряжение",
        value: voltV != null ? `${voltV} В` : "—",
        left: "border-l-violet-500",
        text: "text-violet-800",
      },
      {
        label: "Ток",
        value: curr != null ? `${Math.round(curr)} А` : "—",
        left: "border-l-blue-600",
        text: "text-blue-800",
      },
    ];
  }, [ev, electric]);

  const topWarning = details?.warnings?.[0];

  return (
    <div className="flex min-h-screen flex-col bg-disp-bg text-slate-100">
      <div
        className="pointer-events-none fixed left-0 right-0 top-4 z-[200] flex flex-col items-center gap-2 px-3"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.key}
            className={cn(
              "pointer-events-auto max-w-lg rounded-lg border px-4 py-3 text-sm shadow-xl",
              t.severity === "critical"
                ? "border-red-500 bg-red-950/95 text-red-50"
                : "border-amber-500 bg-amber-950/95 text-amber-50",
            )}
          >
            <p className="font-semibold">{t.title}</p>
          </div>
        ))}
      </div>

      <header className="border-b border-slate-800 bg-[#151b24]">
        <div className="mx-auto flex max-w-[1800px] flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-5">
          <div>
            <h1 className="text-base font-semibold text-slate-100">КТЖ · диспетчеризация</h1>
            <p className="text-xs text-slate-500">Флот и телеметрия в реальном времени</p>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-500">
              {session?.driver.name}
              <span className="text-slate-600"> · </span>
              <span className="text-slate-400">{session?.driver.role}</span>
            </span>
            <button
              type="button"
              onClick={() => void onLogout()}
              className="inline-flex items-center gap-1.5 rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:bg-slate-800/80"
            >
              <LogOut className="h-3.5 w-3.5 opacity-70" />
              Выйти
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1800px] flex-1 flex-col gap-3 px-3 py-3 lg:flex-row lg:px-4">
        <aside className="w-full shrink-0 lg:w-[17rem]">
          <div className="mb-3 flex items-baseline justify-between border-b border-slate-800 pb-2">
            <h2 className="text-sm font-medium text-slate-200">Поезда</h2>
            <span className="text-xs tabular-nums text-slate-500">
              {fleet?.locomotives_online ?? 0} / {fleet?.total_locomotives ?? 0}
            </span>
          </div>
          <ul className="max-h-[38vh] space-y-1.5 overflow-y-auto lg:max-h-[calc(100vh-140px)]">
            {(fleet?.locomotives ?? []).map((l) => (
              <li key={l.locomotive_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(l.locomotive_id)}
                  className={cn(
                    "w-full rounded-md border px-3 py-2.5 text-left transition-colors",
                    selectedId === l.locomotive_id
                      ? "border-slate-500 bg-slate-800/80"
                      : "border-slate-800 bg-[#151b24] hover:border-slate-700",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-[13px] font-medium text-slate-200">
                        {l.locomotive_id}
                      </p>
                      <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-slate-500">
                        {fleetLocoSubtitle(l, routes)}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "mt-0.5 h-2 w-2 shrink-0 rounded-full",
                        l.active_critical_count > 0
                          ? "bg-red-500"
                          : l.active_noncritical_count > 0
                            ? "bg-amber-400"
                            : "bg-emerald-600",
                      )}
                      title={l.is_online ? "Связь есть" : "Нет связи"}
                    />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                    <span className="inline-flex items-center gap-1">
                      <Gauge className="h-3 w-3 opacity-60" />
                      {Math.round(l.speed_kph)} км/ч
                    </span>
                    <span className="tabular-nums text-slate-600">
                      {l.progress_pct != null ? `${Math.round(l.progress_pct)}%` : "—"}
                    </span>
                  </div>
                  {(l.active_critical_count > 0 || l.active_noncritical_count > 0) && (
                    <div className="mt-1.5 flex gap-1.5">
                      {l.active_critical_count > 0 ? (
                        <span className="rounded px-1.5 py-0.5 text-[10px] font-medium text-red-300/90 ring-1 ring-red-900/80">
                          {l.active_critical_count} крит.
                        </span>
                      ) : null}
                      {l.active_noncritical_count > 0 ? (
                        <span className="rounded px-1.5 py-0.5 text-[10px] font-medium text-amber-200/80 ring-1 ring-amber-900/60">
                          {l.active_noncritical_count} вним.
                        </span>
                      ) : null}
                    </div>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="relative min-h-[420px] flex-1 overflow-hidden rounded-lg border border-slate-800 bg-[#0f1419] lg:min-h-[calc(100vh-120px)]">
          <div className="absolute inset-0 z-0">
            <FleetMap
              routes={routes}
              fleet={fleet?.locomotives ?? []}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>

          <div className="relative z-10 flex h-full flex-col p-3 sm:p-4">
            <div className="pointer-events-none flex flex-1 justify-center">
              <div className="pointer-events-auto w-full max-w-2xl rounded-lg border border-slate-200 bg-white p-4 text-slate-900 shadow-lg">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                      <h3 className="font-mono text-lg font-semibold tracking-tight">
                        {selectedFleet?.locomotive_id ?? "—"}
                      </h3>
                    </div>
                    <p className="mt-1 max-w-md text-sm text-slate-600">
                      {selectedFleet ? fleetLocoSubtitle(selectedFleet, routes) : ""}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {(criticalN > 0 || hCat === "Критично") && (
                        <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-bold text-white">
                          КРИТИЧНО
                        </span>
                      )}
                      {healthScore != null && (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold",
                            hCat === "Критично"
                              ? "bg-red-100 text-red-800"
                              : hCat === "Внимание"
                                ? "bg-amber-100 text-amber-900"
                                : "bg-emerald-100 text-emerald-800",
                          )}
                        >
                          <Activity className="h-3.5 w-3.5" />
                          {Math.round(healthScore)}%
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setExpanded((e) => !e)}
                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50"
                  >
                    {expanded ? "Свернуть" : "Развернуть"}
                    {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={!selectedId || reportBusy}
                    onClick={() => void onExportReport()}
                    className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Download className="h-3.5 w-3.5" />
                    {reportBusy ? "Формирование…" : "Отчёт за 15 мин (PDF)"}
                  </button>
                  {reportErr ? (
                    <span className="text-xs text-red-600">{reportErr}</span>
                  ) : null}
                </div>

                {expanded ? (
                  <>
                    <div className="mt-4">
                      <RouteStatusBar event={ev} routeTitle={routeTitle} />
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
                      {metrics.map((m) => (
                        <div
                          key={m.label}
                          className={cn(
                            "rounded border border-slate-200 border-l-[3px] bg-slate-50/50 px-2 py-2",
                            m.left,
                          )}
                        >
                          <p className="text-[10px] font-medium text-slate-500">{m.label}</p>
                          <p className={cn("mt-0.5 text-sm font-semibold tabular-nums", m.text)}>{m.value}</p>
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 rounded-md border border-slate-200 border-l-[3px] border-l-red-500 bg-slate-50 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-700">Оповещения</span>
                        <div className="flex gap-2 text-[11px]">
                          <span className="text-red-700">{criticalN} критич.</span>
                          <span className="text-amber-800">{otherN} предупр.</span>
                        </div>
                      </div>
                      {topWarning ? (
                        <p className="mt-2 text-sm text-slate-800">{topWarning.title}</p>
                      ) : (
                        <p className="mt-2 text-sm text-slate-500">Нет активных оповещений</p>
                      )}
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
