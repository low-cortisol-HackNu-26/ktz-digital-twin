"use client";

import { useMemo } from "react";
import {
  RadialBar,
  RadialBarChart,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import { useMockDashboardStore } from "@/store/mockDashboardStore";
import {
  formatFuel,
  formatPressure,
  formatSpeed,
  formatTemp,
  formatVoltage,
  cn,
} from "@/lib/utils";
import { format } from "date-fns";

function HealthCheckView() {
  const packet = useMockDashboardStore((s) => s.packet);
  const health = useMockDashboardStore((s) => s.health);

  const gaugeData = useMemo(
    () => [{ name: "score", value: health.score, fill: gaugeColor(health.score) }],
    [health.score],
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-20 lg:grid-cols-2">
        <section
          className={cn(
            "panel relative overflow-hidden lg:col-span-1 h-fit justify-self-end",
            health.category === "Критично" && "animate-critical-pulse border-health-critical/60",
            health.category === "Внимание" && "border-health-warning/50",
            health.category === "Норма" && "border-health-normal/30",
          )}
        >
          <div className="mt-0 flex items-center gap-6">
            <div className="h-80 w-80 shrink-0 relative mx-auto">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart
                  innerRadius="80%"
                  outerRadius="100%"
                  data={gaugeData}
                  startAngle={90}
                  endAngle={-270}
                >
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar
                    background={{ fill: "rgba(148,163,184,0.12)" }}
                    dataKey="value"
                    cornerRadius={20}
                  />
                </RadialBarChart>
              </ResponsiveContainer>
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
              <p className={cn(
                  "mt-2 inline-flex rounded-md px-2 py-1 text-7xl font-semibold uppercase",
                  health.category === "Норма" && "text-emerald-500",
                  health.category === "Внимание" && "text-amber-500",
                  health.category === "Критично" && "text-red-500",
                )}>{health.score}</p>
                <p className="text-xs text-secondary">
                  Индекс здоровья
                </p>
              <p
                className={cn(
                  "mt-2 inline-flex rounded-full px-3 py-1 text-lg font-semibold tracking-wide",
                  health.category === "Норма" && "bg-emerald-500/15 text-emerald-500",
                  health.category === "Внимание" && "bg-amber-500/15 text-amber-500",
                  health.category === "Критично" && "bg-rose-500/15 text-red-500 ring-1 ring-red-500",
                )}
              >
                {health.category}
              </p>
              <p className="text-xs text-secondary mt-2">Улучшается</p>
            </div>
            </div>
          </div>
        </section>
        <section className="panel relative overflow-hidden lg:col-span-1 justify-self-start flex items-center justify-center">
          <img src="/images/speed.svg" alt="Speed" className="w-80 h-64 " />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
          <p className="text-6xl font-semibold text-primary mt-10">{packet.speed.toPrecision(3)}</p>
          <p className="text-xs text-primary">км/ч</p>
          </div>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
          <p className="text-2xl font-semibold text-primary mt-20">130</p>
          </div>
          <div className="absolute border-[6px] border-red-500 rounded-full w-16 h-16 bottom-0 mb-10"></div>
        </section>
        {/*<section className="panel lg:col-span-2">
          <h2 className="text-sm font-medium text-slate-400">Live telemetry</h2>
          <p className="mt-1 text-xs text-slate-500">
            Values after mock EMA smoothing (temperature, brake pressure, voltage).
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <MetricCard label="Speed" value={formatSpeed(packet.speed)} />
            <MetricCard label="Fuel" value={formatFuel(packet.fuel)} />
            <MetricCard label="Engine temp" value={formatTemp(packet.temp_engine)} />
            <MetricCard
              label="Brake pressure"
              value={formatPressure(packet.pressure_brake)}
            />
            <MetricCard label="Traction voltage" value={formatVoltage(packet.voltage)} />
            <MetricCard
              label="Active alert codes"
              value={
                packet.alert_codes.length
                  ? packet.alert_codes.join(", ")
                  : "None"
              }
              emphasize={packet.alert_codes.length > 0}
            />
          </div>
        </section>*/}
      </div>

      <section className="panel">
        <h2 className="text-sm font-medium text-slate-400">Packet shape (wire)</h2>
        <p className="mt-1 text-xs text-slate-500">
          Same JSON fields the simulator will send over WebSocket later.
        </p>
        <pre className="readout-sm mt-4 max-h-64 overflow-auto rounded-lg bg-black/40 p-4 text-slate-300">
          {JSON.stringify(packet, null, 2)}
        </pre>
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

function MetricCard({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-cabin-border bg-cabin-bg/50 p-4",
        emphasize && "border-amber-500/40 bg-amber-500/5",
      )}
    >
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="readout mt-2 text-xl">{value}</p>
    </div>
  );
}
