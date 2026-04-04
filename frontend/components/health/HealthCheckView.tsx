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

export function HealthCheckView() {
  const packet = useMockDashboardStore((s) => s.packet);
  const health = useMockDashboardStore((s) => s.health);

  const gaugeData = useMemo(
    () => [{ name: "score", value: health.score, fill: gaugeColor(health.score) }],
    [health.score],
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-3">
        <section
          className={cn(
            "panel relative overflow-hidden lg:col-span-1",
            health.category === "CRITICAL" && "animate-critical-pulse border-health-critical/60",
            health.category === "WARNING" && "border-health-warning/50",
            health.category === "NORMAL" && "border-health-normal/30",
          )}
        >
          <h2 className="text-sm font-medium text-slate-400">Health index</h2>
          <p className="mt-1 text-xs text-slate-500">
            Mock engine — mirrors weighted score + penalties from alerts (no API).
          </p>
          <div className="mt-4 flex items-center gap-6">
            <div className="h-44 w-44 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart
                  innerRadius="68%"
                  outerRadius="100%"
                  data={gaugeData}
                  startAngle={90}
                  endAngle={-270}
                >
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar
                    background={{ fill: "rgba(148,163,184,0.12)" }}
                    dataKey="value"
                    cornerRadius={6}
                  />
                </RadialBarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="readout text-4xl text-white">{health.score}</p>
              <p
                className={cn(
                  "mt-2 inline-flex rounded-md px-2 py-1 text-xs font-semibold uppercase tracking-wide",
                  health.category === "NORMAL" && "bg-emerald-500/15 text-emerald-300",
                  health.category === "WARNING" && "bg-amber-500/15 text-amber-200",
                  health.category === "CRITICAL" && "bg-rose-500/15 text-rose-200",
                )}
              >
                {health.category}
              </p>
              <p className="readout-sm mt-3">
                Updated{" "}
                {health.timestamp
                  ? format(new Date(health.timestamp), "HH:mm:ss.SSS")
                  : "—"}
              </p>
            </div>
          </div>
          <ul className="mt-6 space-y-2 border-t border-cabin-border pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Top factors
            </p>
            {health.factors.map((f) => (
              <li key={f} className="text-sm text-slate-300">
                <span className="text-sky-400">· </span>
                {f}
              </li>
            ))}
          </ul>
        </section>

        <section className="panel lg:col-span-2">
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
        </section>
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
