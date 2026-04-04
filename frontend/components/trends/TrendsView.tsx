"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import { useMockDashboardStore } from "@/store/mockDashboardStore";

export function TrendsView() {
  const history = useMockDashboardStore((s) => s.history);

  const data = useMemo(
    () =>
      history.map((p) => ({
        ...p,
        label: format(new Date(p.t), "HH:mm:ss"),
      })),
    [history],
  );

  return (
    <section className="panel flex h-[min(720px,calc(100vh-200px))] flex-col">
      <div className="mb-4 shrink-0">
        <h2 className="text-sm font-medium text-slate-400">Trends</h2>
        <p className="mt-1 text-xs text-slate-500">
          Rolling window from the mock store (~2 minutes at 1 Hz). Mirrors live charts
          you will wire to Redis / Timescale later.
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="4 4" />
            <XAxis
              dataKey="label"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              interval="preserveStartEnd"
              minTickGap={24}
            />
            <YAxis
              yAxisId="left"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              domain={["auto", "auto"]}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#e2e8f0" }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="speed"
              name="Speed (km/h)"
              stroke="#38bdf8"
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="temp_engine"
              name="Engine °C"
              stroke="#f97316"
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="pressure_brake"
              name="Brake bar"
              stroke="#a855f7"
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="voltage"
              name="Voltage V"
              stroke="#22c55e"
              dot={false}
              strokeWidth={2}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
