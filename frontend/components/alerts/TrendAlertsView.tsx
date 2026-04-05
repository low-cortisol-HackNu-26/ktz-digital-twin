"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import { useMockDashboardStore } from "@/store/mockDashboardStore";

function TrendAlertsView() {
  const history = useMockDashboardStore((s) => s.history);

  const chartData = useMemo(() => {
    const last = history.slice(-40);
    return last.map((p) => ({
      t: p.t,
      label: format(new Date(p.t), "HH:mm:ss"),
      speed: p.speed,
      hasAlert: p.temp_engine > 98 || p.pressure_brake < 4.2 || p.voltage < 22 ? 1 : 0,
    }));
  }, [history]);

  return (
    <div className="space-y-6">
      <section className="panel flex h-[min(360px,50vh)] flex-col">
        <div className="mb-4 shrink-0">
          <h2 className="text-sm font-medium text-slate-400">Alert correlation</h2>
          <p className="mt-1 text-xs text-slate-500">
            Bars mark seconds where mock thresholds would breach (E012 / B044 / V201).
            Active warnings use{" "}
            <code className="text-slate-400">GET /api/locomotives/{"{id}"}/warnings</code> on
            the Alerts tab.
          </p>
        </div>
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="4 4" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                interval="preserveStartEnd"
                minTickGap={16}
              />
              <YAxis
                yAxisId="speed"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                domain={["auto", "auto"]}
              />
              <YAxis
                yAxisId="flag"
                orientation="right"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                domain={[0, 1]}
                ticks={[0, 1]}
              />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar
                yAxisId="speed"
                dataKey="speed"
                name="Speed"
                fill="rgba(56,189,248,0.35)"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                yAxisId="flag"
                dataKey="hasAlert"
                name="Threshold breach"
                fill="rgba(248,113,113,0.9)"
                radius={[2, 2, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

export default TrendAlertsView;
export { TrendAlertsView };
