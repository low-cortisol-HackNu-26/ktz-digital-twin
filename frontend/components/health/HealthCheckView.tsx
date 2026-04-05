"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  RadialBar,
  RadialBarChart,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import {
  useLocomotiveTelemetryHealth,
  resolveHealthLocomotiveId,
} from "@/hooks/useLocomotiveTelemetryHealth";
import type { TelemetryEventCurrent } from "@/lib/telemetryApi";
import {
  BRAKES_TEMP_CRIT_C,
  BRAKES_TEMP_WARN_C,
  CURRENT_CRIT_A,
  CURRENT_WARN_A,
  DRIVE_TEMP_CRIT_C,
  DRIVE_TEMP_WARN_C,
  ENERGY_ABS_CRIT,
  ENERGY_ABS_WARN,
  FUEL_PCT_CRIT_BELOW,
  FUEL_PCT_WARN_BELOW,
  PNEUMATIC_CRIT_BAR,
  PNEUMATIC_WARN_BAR,
  VOLTAGE_CRIT_KV,
  VOLTAGE_WARN_KV,
} from "@/lib/telemetryThresholds";
import { cn } from "@/lib/utils";
import {
  AlertCircle,
  BatteryCharging,
  Cable,
  Cog,
  Droplet,
  Gauge,
  Plug,
  Thermometer,
  Wind,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

function HealthCheckView() {
  const locomotiveId = resolveHealthLocomotiveId();
  const { current, health, loading, fetchFailed } =
    useLocomotiveTelemetryHealth(locomotiveId);

  const event = current?.event;

  const speedDisplay = event != null ? (event.speed_kph).toPrecision(3) : "—";
  const allowedDisplay =
    event != null &&
    typeof event.allowed_speed_kph === "number" &&
    event.allowed_speed_kph > 0
      ? Math.round(event.allowed_speed_kph).toString()
      : "—";

  const overspeed =
    event != null &&
    typeof event.allowed_speed_kph === "number" &&
    event.allowed_speed_kph > 0 &&
    event.speed_kph > event.allowed_speed_kph;

  const wirePayload = useMemo(() => {
    if (current) return current;
    return {
      locomotive_id: locomotiveId,
      note: fetchFailed
        ? "Запрос /current завершился с ошибкой или сеть недоступна."
        : loading
          ? "Загрузка…"
          : "Нет данных.",
    };
  }, [current, locomotiveId, fetchFailed, loading]);

  const gaugeData = useMemo(
    () => [
      {
        name: "score",
        value: health.score,
        fill: gaugeColor(health.score),
      },
    ],
    [health.score],
  );

  const speedGauge = useMemo(
    () => [
      {
        name: "score",
        value: 100,
        fill: overspeed
          ? "oklch(63.7% 0.237 25.331)"
          : "oklch(69.6% 0.17 162.48)",
      },
    ],
    [overspeed],
  );

  const speedKphForNeedle =
    event != null && typeof event.speed_kph === "number"
      ? Math.min(160, Math.max(0, event.speed_kph))
      : 0;

  const gaugeTrackColor =
    health.category === "Критично"
      ? "rgba(255,255,255,0.9)"
      : health.category === "Внимание"
        ? "rgba(255,255,255,0.9)"
        : "rgba(255,255,255,0.92)";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2 ">
        <div
          className={cn(
            "rounded-xl p-2",
            health.category === "Норма" && "animate-health-halo-normal",
            health.category === "Внимание" && "animate-health-halo-warning",
            health.category === "Критично" && "animate-health-halo-critical",
          )}
        >
        <section
          className={cn(
            "w-full relative overflow-hidden col-span-1 rounded-lg border-2 bg-slate-100/40 h-[350px]",
            health.category === "Критично" && "border-red-500/80",
            health.category === "Внимание" && "border-amber-400/85",
            health.category === "Норма" && "border-emerald-500/50",
          )}
        >
          <div className="mt-[0] flex items-center w-full">
            <div className="relative mx-auto aspect-square w-[399px] mt-[-10px]">
              <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                    data={gaugeData}
                    innerRadius="72%"
                    outerRadius="95%"
                    startAngle={220}
                    endAngle={-40}
                  >
                    <PolarAngleAxis
                      type="number"
                      domain={[0, 100]}
                      tick={false}
                      axisLine={false}
                    />
                    <RadialBar
                      dataKey="value"
                      cornerRadius={0}
                      background={{ fill: gaugeTrackColor }}
                      stroke="white"
                      strokeWidth={4}
                    />
                  </RadialBarChart>
                </ResponsiveContainer>
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
                <p
                  className={cn(
                    "mt-2 inline-flex rounded-md px-2 py-1 text-7xl font-semibold uppercase text-white"
                  )}
                >
                  {health.score}
                </p>
                <p className="text-xs text-white">Индекс здоровья</p>
                <p
                  className={cn(
                    "mt-2 inline-flex rounded-full px-3 py-1 text-lg font-semibold tracking-wide bg-white",
                    health.category === "Норма" &&
                      "text-emerald-500 ring-1 ring-emerald-500",
                    health.category === "Внимание" &&
                      "text-amber-500 ring-1 ring-amber-500",
                    health.category === "Критично" &&
                      "text-red-500 ring-1 ring-red-500",
                  )}
                >
                  {health.category}
                </p>
              </div>
            </div>
          </div>
        </section>
        </div>
        <section className="w-full relative  lg:col-span-1 bg-slate-100/40 rounded-lg flex items-center justify-center  h-max-[200px]">
          <img src="/images/speed.svg" alt="Speed" className="w-80 h-64 z-2" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
            <p className="text-5xl font-semibold text-white mt-10">
              {speedDisplay}
            </p>
            <p className="text-xs text-white">км/ч</p>
          </div>
          <div className="absolute bg-white border-[6px] border-red-500 rounded-full w-16 h-16 bottom-0 mb-4" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
            <p className="text-2xl font-semibold text-primary mt-8">
              {allowedDisplay}
            </p>
          </div>
          <div className="absolute mx-auto aspect-square w-[376px] mt-[44px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                data={speedGauge}
                innerRadius="72%"
                outerRadius="80%"
                startAngle={225}
                endAngle={-45}
              >
                <PolarAngleAxis
                  type="number"
                  domain={[0, 100]}
                  tick={false}
                  axisLine={false}
                />
                <RadialBar
                  dataKey="value"
                  cornerRadius={0}
                  background={{ fill: gaugeTrackColor }}
                />
              </RadialBarChart>
            </ResponsiveContainer>
            <SpeedometerNeedle speedKph={speedKphForNeedle} maxKph={160} />
          </div>
        </section>
      </div>
      <section className="rounded-xl border border-cyan-950/50 bg-slate-100/40 p-5 shadow-inner">
        <TelemetryMetricsGrid event={event} overspeed={overspeed} />
      </section>
    </div>
  );
}

export default HealthCheckView;
export { HealthCheckView };

function gaugeColor(score: number) {
  if (score < 45) return "#ef4444";
  if (score < 72) return "#eab308";
  return "#22c55e";
}

type PanelSeverity = "normal" | "warning" | "critical";

function formatTelemetryNum(n: number | undefined | null, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

function maxDriveTempC(e: TelemetryEventCurrent): number | null {
  const vals = [
    e.transformer_temp_c,
    e.converter_temp_c,
    e.traction_motor_temp_c,
  ].filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
  if (vals.length === 0) return null;
  return Math.max(...vals);
}

function driveTempSeverity(temp: number | null): PanelSeverity {
  if (temp == null) return "normal";
  if (temp >= DRIVE_TEMP_CRIT_C) return "critical";
  if (temp >= DRIVE_TEMP_WARN_C) return "warning";
  return "normal";
}

function brakePipeSeverity(temp: number | undefined): PanelSeverity {
  if (temp == undefined) return "normal";
  if (temp >= BRAKES_TEMP_CRIT_C) return "critical";
  if (temp >= BRAKES_TEMP_WARN_C) return "warning";
  return "normal";
}

function pneumaticSeverity(bar: number | undefined): PanelSeverity {
  if (bar == null || Number.isNaN(bar)) return "normal";
  if (bar < PNEUMATIC_CRIT_BAR) return "critical";
  if (bar < PNEUMATIC_WARN_BAR) return "warning";
  return "normal";
}

function voltageSeverity(kv: number | undefined): PanelSeverity {
  if (kv == null || Number.isNaN(kv)) return "normal";
  if (kv < VOLTAGE_CRIT_KV) return "critical";
  if (kv < VOLTAGE_WARN_KV) return "warning";
  return "normal";
}

function electricitySeverity(
  e: number | undefined,
): PanelSeverity {
  if (e == null || Number.isNaN(e)) return "normal";
  const a = Math.abs(e);
  if (a >= ENERGY_ABS_CRIT) return "critical";
  if (a >= ENERGY_ABS_WARN) return "warning";
  return "normal";
}

function fuelSeverity(
  e: number | undefined
): PanelSeverity {
  if (e == null || Number.isNaN(e)) return "critical";
  const a = Math.abs(e);
  if (a >= FUEL_PCT_WARN_BELOW) return "normal";
  if (a >= FUEL_PCT_CRIT_BELOW) return "warning";
  return "critical";
}

function currentSeverity(amps: number | undefined): PanelSeverity {
  if (amps == null || Number.isNaN(amps)) return "normal";
  const a = Math.abs(amps);
  if (a >= CURRENT_CRIT_A) return "critical";
  if (a >= CURRENT_WARN_A) return "warning";
  return "normal";
}

function TelemetryMetricsGrid({
  event,
  overspeed,
}: {
  event: TelemetryEventCurrent | null | undefined;
  overspeed: boolean;
}) {
  if (event == null) {
    return (
      <p className="py-10 text-center text-sm text-slate-400">
        Нет данных телеметрии (ожидается событие из /current).
      </p>
    );
  }

  const driveTemp = maxDriveTempC(event);

  const panels: {
    label: string;
    value: string;
    unit: string;
    severity: PanelSeverity;
    Icon: LucideIcon;
  }[] = [
    {
      label: event.traction_type=="electric" ? "ЭЛЕКТРИЧЕСТВО": "ТОПЛИВО",
      value: event.traction_type=="electric" ? formatTelemetryNum(event.energy_consumption_kwh, 0):formatTelemetryNum(event.fuel_level_percent, 0),
      unit: event.traction_type=="electric" ? "W":"L",
      severity: event.traction_type=="electric" ? electricitySeverity(event.energy_consumption_kwh) : fuelSeverity(event.fuel_level_percent),
      Icon: event.traction_type=="electric" ? BatteryCharging: Droplet,
    },
    {
      label: "ДВИГ. °C",
      value: driveTemp != null ? formatTelemetryNum(driveTemp, 1) : "—",
      unit: "°C",
      severity: driveTempSeverity(driveTemp),
      Icon: Cog,
    },
    {
      label: "ТОРМОЗ °C",
      value: formatTelemetryNum(event.brakes_temperature_c, 1),
      unit: "°C",
      severity: brakePipeSeverity(event.brakes_temperature_c),
      Icon: AlertCircle,
    },
    {
      label: "ДАВЛЕНИЕ",
      value: formatTelemetryNum(event.pneumatic_pressure_bar, 1),
      unit: "bar",
      severity: pneumaticSeverity(event.pneumatic_pressure_bar),
      Icon: Gauge,
    },
    {
      label: "НАПРЯЖЕНИЕ",
      value: formatTelemetryNum(event.catenary_voltage_kv, 1),
      unit: "кВ",
      severity: voltageSeverity(event.catenary_voltage_kv),
      Icon: Plug,
    },
    {
      label: "ТОК",
      value: formatTelemetryNum(event.traction_current_a, 0),
      unit: "А",
      severity: currentSeverity(event.traction_current_a),
      Icon: Zap,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
      {panels.map((p) => (
        <TelemetryPanel key={p.label} {...p} />
      ))}
    </div>
  );
}

function TelemetryPanel({
  label,
  value,
  unit,
  severity,
  Icon,
}: {
  label: string;
  value: string;
  unit: string;
  severity: PanelSeverity;
  Icon: LucideIcon;
}) {
  return (
    <div
      className={cn(
        "flex min-h-[104px] items-center justify-between gap-3 rounded-xl bg-white px-4 py-3 transition-shadow duration-300",
        severity === "normal" &&
          "ring-1 ring-slate-200/90 shadow-sm shadow-slate-200/40 ",
        severity === "warning" &&
          "border-4 border-amber-500 ring-amber-500 animate-panel-glow-warning ",
        severity === "critical" && "border-8 border-red-500 ring-red-500 animate-panel-glow-critical",
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="text-2xl font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </p>
        <p className="mt-1 flex flex-wrap items-baseline gap-1.5">
          <span className="text-6xl font-bold tabular-nums text-slate-800">
            {value}
          </span>
          <span className="text-base font-semibold text-slate-600">{unit}</span>
        </p>
      </div>
      <div
        className={cn(
          "flex h-12 w-12 shrink-0 items-center justify-center rounded-lg mr-4",
          severity === "normal" && "text-emerald-600",
          severity === "warning" && "text-amber-500",
          severity === "critical" && "text-red-500",
        )}
      >
        <Icon className="h-16 w-16 stroke-[2.0]" aria-hidden />
      </div>
    </div>
  );
}

/** Same polar convention as Recharts RadialBarChart (see PolarUtils). */
function polarToCartesian(
  cx: number,
  cy: number,
  radius: number,
  angleDeg: number,
): { x: number; y: number } {
  const rad = (Math.PI / 180) * angleDeg;
  return {
    x: cx + Math.cos(-rad) * radius,
    y: cy + Math.sin(-rad) * radius,
  };
}

const SPEED_GAUGE_START = 225;
const SPEED_GAUGE_END = -45;

/** Ease current → target each frame (higher = snappier, lower = smoother). */
const NEEDLE_BLEND = 0.14;
const NEEDLE_EPS_DEG = 0.06;

function needleAngleFromSpeed(speedKph: number, maxKph: number): number {
  const t = maxKph > 0 ? Math.min(1, Math.max(0, speedKph / maxKph)) : 0;
  return SPEED_GAUGE_START + t * (SPEED_GAUGE_END - SPEED_GAUGE_START);
}

function useSmoothedNeedleAngle(targetDeg: number): number {
  const [displayDeg, setDisplayDeg] = useState(targetDeg);
  const displayRef = useRef(targetDeg);
  const targetRef = useRef(targetDeg);
  targetRef.current = targetDeg;

  useEffect(() => {
    let raf = 0;

    const step = () => {
      const goal = targetRef.current;
      let cur = displayRef.current;
      const delta = goal - cur;
      if (Math.abs(delta) < NEEDLE_EPS_DEG) {
        if (cur !== goal) {
          cur = goal;
          displayRef.current = cur;
          setDisplayDeg(cur);
        }
        return;
      }
      cur += delta * NEEDLE_BLEND;
      displayRef.current = cur;
      setDisplayDeg(cur);
      raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [targetDeg]);

  return displayDeg;
}

/**
 * Needle for 0–maxKph over the arc startAngle → endAngle (matches RadialBarChart).
 */
function SpeedometerNeedle({
  speedKph,
  maxKph,
}: {
  speedKph: number;
  maxKph: number;
}) {
  const targetDeg = needleAngleFromSpeed(speedKph, maxKph);
  const angleDeg = useSmoothedNeedleAngle(targetDeg);
  const gradId = useId().replace(/:/g, "");

  const cx = 100;
  const cy = 100;

  const inner = polarToCartesian(cx, cy, 30, angleDeg);
  const tip = polarToCartesian(cx, cy, 70, angleDeg);

  return (
    <svg
      className="pointer-events-none absolute inset-0 z-10 h-full w-full"
      viewBox="0 0 200 200"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden
    >
      <defs>
        <linearGradient
          id={gradId}
          gradientUnits="userSpaceOnUse"
          x1={inner.x}
          y1={inner.y}
          x2={tip.x}
          y2={tip.y}
        >
          <stop offset="0%" stopColor="transparent" />
          <stop offset="20%" stopColor="transparent" />
          <stop offset="100%" stopColor="black" />
        </linearGradient>
      </defs>

      <line
        x1={inner.x}
        y1={inner.y}
        x2={tip.x}
        y2={tip.y}
        stroke={`url(#${gradId})`}
        strokeWidth={3.5}
        strokeLinecap="round"
      />
    </svg>
  );
}