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
import { cn } from "@/lib/utils";

function TrendAlertsView() {
  const alertLog = useMockDashboardStore((s) => s.alertLog);
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
            Bars mark seconds where mock thresholds would raise codes (E012 / B044 /
            V201). Feed will come from FastAPI + Celery later.
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

      <section className="panel">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium text-slate-400">Alert stream</h2>
            <p className="mt-1 text-xs text-slate-500">
              Newest first — populated when the simulator injects fault codes.
            </p>
          </div>
          <span className="readout-sm text-slate-500">{alertLog.length} events</span>
        </div>
        <ul className="mt-4 max-h-[420px] space-y-2 overflow-auto pr-1">
          {alertLog.length === 0 ? (
            <li className="rounded-lg border border-dashed border-cabin-border bg-cabin-bg/40 px-4 py-8 text-center text-sm text-slate-500">
              No alerts yet. Wait for a temperature spike or brake dip in the mock feed.
            </li>
          ) : (
            alertLog.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cabin-border bg-cabin-bg/50 px-4 py-3"
              >
                <div>
                  <p className="font-mono text-sm font-semibold text-sky-300">{a.code}</p>
                  <p className="text-sm text-slate-300">{a.message}</p>
                </div>
                <div className="text-right">
                  <span
                    className={cn(
                      "inline-flex rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                      a.severity === "CRITICAL" && "bg-rose-500/15 text-rose-200",
                      a.severity === "WARNING" && "bg-amber-500/15 text-amber-200",
                      a.severity === "NORMAL" && "bg-emerald-500/15 text-emerald-200",
                    )}
                  >
                    {a.severity}
                  </span>
                  <p className="readout-sm mt-1 text-slate-500">
                    {format(new Date(a.time), "HH:mm:ss")}
                  </p>
                </div>
              </li>
            ))
          )}
        </ul>
      </section>
    </div>
  );
}

export default TrendAlertsView;
export { TrendAlertsView };
