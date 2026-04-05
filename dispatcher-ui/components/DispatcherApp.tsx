"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Download,
  Gauge,
  LogOut,
  Train,
  Zap,
} from "lucide-react";
import {
  fetchBackendCurrent,
  type LocomotiveCurrentResponse,
} from "@/lib/telemetryBackend";
import {
  fetchDispatcherFleet,
  fetchDispatcherMapRoutes,
  fetchLocomotiveDetails,
  type FleetStatusResponse,
  type LocoDetailsWarning,
  type LocoStatusInfo,
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
const CLIENT_BASE = (process.env.NEXT_PUBLIC_CLIENT_APP_URL ?? "http://localhost:3000").replace(
  /\/$/,
  "",
);

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
    async function loadRoutesOnce() {
      const r = await fetchDispatcherMapRoutes();
      if (!cancelled) setRoutes(r);
    }
    void loadRoutesOnce();
    return () => {
      cancelled = true;
    };
  }, [session]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    async function tick() {
      const f = await fetchDispatcherFleet();
      if (!cancelled) setFleet(f);
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

  const routeTitle =
    selectedFleet?.route_name?.trim() ||
    selectedFleet?.route_code?.trim() ||
    ev?.route_segment?.split(":")[0]?.toUpperCase() ||
    "—";

  const criticalN = selectedFleet?.active_critical_count ?? 0;
  const otherN = selectedFleet?.active_noncritical_count ?? 0;

  async function onLogout() {
    await logoutDispatcher();
    router.replace("/login");
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
        border: "border-sky-500",
        text: "text-sky-600",
      },
      {
        label: electric ? "Энергия" : "Топливо",
        value: fuelOrEnergy,
        border: "border-amber-500",
        text: "text-amber-600",
      },
      {
        label: "Температура",
        value: temp != null ? `${temp.toFixed(0)} °C` : "—",
        border: "border-red-500",
        text: "text-red-600",
      },
      {
        label: "Мощность",
        value: power != null ? `${Math.round(power)} кВт` : "—",
        border: "border-emerald-500",
        text: "text-emerald-600",
      },
      {
        label: "Напряжение",
        value: voltV != null ? `${voltV} В` : "—",
        border: "border-violet-500",
        text: "text-violet-600",
      },
      {
        label: "Ток",
        value: curr != null ? `${Math.round(curr)} А` : "—",
        border: "border-blue-500",
        text: "text-blue-600",
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

      <header className="border-b border-white/10 bg-disp-panel/90 px-4 py-3 backdrop-blur sm:px-6">
        <div className="mx-auto flex max-w-[1920px] flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-disp-accent/20 text-disp-accent">
              <Zap className="h-6 w-6" aria-hidden />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">КТЖ Цифровой Двойник</h1>
              <p className="text-xs text-slate-400">Система мониторинга локомотивов — диспетчерская</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-slate-400">
              {session?.driver.name} · <span className="text-disp-accent">{session?.driver.role}</span>
            </span>
            <Link
              href={CLIENT_BASE}
              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/5"
            >
              Клиент (киоск)
            </Link>
            <button
              type="button"
              onClick={() => void onLogout()}
              className="inline-flex items-center gap-1 rounded-lg bg-red-600/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-500"
            >
              <LogOut className="h-3.5 w-3.5" />
              Выход
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1920px] flex-1 flex-col gap-3 px-3 py-3 lg:flex-row lg:gap-4 lg:px-4 lg:py-4">
        <aside className="w-full shrink-0 lg:w-72">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-disp-accent">
              Активные поезда
            </h2>
            <span className="text-xs text-slate-500">
              {fleet?.locomotives_online ?? 0} онлайн
            </span>
          </div>
          <ul className="max-h-[40vh] space-y-2 overflow-y-auto lg:max-h-[calc(100vh-200px)]">
            {(fleet?.locomotives ?? []).map((l) => (
              <li key={l.locomotive_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(l.locomotive_id)}
                  className={cn(
                    "w-full rounded-xl border p-3 text-left transition-colors",
                    selectedId === l.locomotive_id
                      ? "border-disp-accent bg-disp-accent/10 shadow-[0_0_0_1px_rgba(79,179,232,0.4)]"
                      : "border-white/10 bg-disp-panel/60 hover:border-white/20",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-mono text-sm font-semibold text-white">{l.locomotive_id}</p>
                      <p className="line-clamp-1 text-xs text-slate-400">
                        {l.route_name || l.route_code || "—"}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
                        l.active_critical_count > 0
                          ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"
                          : l.active_noncritical_count > 0
                            ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                            : "bg-emerald-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]",
                      )}
                    />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Gauge className="h-3.5 w-3.5 text-disp-accent" />
                      {Math.round(l.speed_kph)} км/ч
                    </span>
                    <span>{l.progress_pct != null ? `${Math.round(l.progress_pct)}%` : "—"}</span>
                  </div>
                  <div className="mt-2 flex gap-2">
                    {l.active_critical_count > 0 ? (
                      <span className="rounded bg-red-600/30 px-2 py-0.5 text-[10px] font-bold text-red-200">
                        ▲ {l.active_critical_count}
                      </span>
                    ) : null}
                    {l.active_noncritical_count > 0 ? (
                      <span className="rounded bg-amber-600/25 px-2 py-0.5 text-[10px] font-bold text-amber-100">
                        ! {l.active_noncritical_count}
                      </span>
                    ) : null}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="relative min-h-[420px] flex-1 overflow-hidden rounded-2xl border border-white/10 bg-[#0d1218] lg:min-h-[calc(100vh-200px)]">
          <div className="absolute inset-0 z-0">
            <FleetMap
              routes={routes}
              fleet={fleet?.locomotives ?? []}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>

          <div className="relative z-10 flex h-full flex-col justify-between p-3 sm:p-4">
            <div className="pointer-events-none flex justify-center">
              <div className="pointer-events-auto w-full max-w-3xl rounded-2xl border border-white/10 bg-white p-4 text-slate-900 shadow-2xl">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Train className="h-5 w-5 text-slate-600" />
                      <h3 className="text-xl font-bold">{selectedFleet?.locomotive_id ?? "—"}</h3>
                      <span className="text-slate-500">
                        {selectedFleet?.route_name || selectedFleet?.display_name || ""}
                      </span>
                    </div>
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
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                  >
                    {expanded ? "Свернуть" : "Развернуть"}
                    {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </button>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled
                    className="inline-flex items-center gap-2 rounded-lg bg-disp-accent px-3 py-2 text-xs font-medium text-white opacity-60"
                    title="В разработке"
                  >
                    <Download className="h-4 w-4" />
                    Экспорт отчёта
                  </button>
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
                            "rounded-xl border-2 bg-white px-2 py-2 text-center",
                            m.border,
                          )}
                        >
                          <p className="text-[9px] font-bold uppercase tracking-wide text-slate-500">
                            {m.label}
                          </p>
                          <p className={cn("mt-1 text-sm font-bold sm:text-base", m.text)}>{m.value}</p>
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 rounded-xl border-l-4 border-red-500 bg-slate-50 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase text-slate-700">
                          Активные оповещения
                        </span>
                        <div className="flex gap-2">
                          <span className="rounded bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white">
                            {criticalN} критично
                          </span>
                          <span className="rounded bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">
                            {otherN} предупреждение
                          </span>
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

      <nav className="border-t border-white/10 bg-disp-panel px-2 py-2">
        <div className="mx-auto flex max-w-[1920px] flex-wrap items-center justify-between gap-2">
          <div className="flex flex-1 flex-wrap justify-center gap-1 sm:gap-2">
            {[
              { n: 1, label: "Здоровье и метрики", href: `${CLIENT_BASE}/dashboard/health` },
              { n: 2, label: "Оповещения", href: `${CLIENT_BASE}/dashboard/alerts` },
              { n: 3, label: "Тренды систем", href: `${CLIENT_BASE}/dashboard/trends` },
              { n: 4, label: "Карта маршрута", href: `${CLIENT_BASE}/dashboard/map` },
              { n: 5, label: "Диспетчер", href: "/dispatcher", active: true },
            ].map((tab) => (
              <Link
                key={tab.n}
                href={tab.href}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium sm:text-sm",
                  tab.active
                    ? "bg-disp-accent text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-white",
                )}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-black/20 text-[10px]">
                  {tab.n}
                </span>
                {tab.label}
              </Link>
            ))}
          </div>
        </div>
        <p className="mt-1 text-center text-[10px] text-slate-500">
          Вкладки 1–4 открывают киоск на порту 3000 · эта страница — диспетчерская (3001)
        </p>
      </nav>
    </div>
  );
}
