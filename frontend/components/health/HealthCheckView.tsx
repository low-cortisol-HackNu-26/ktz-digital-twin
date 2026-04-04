"use client";

import { useMemo } from "react";
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
import { formatSpeed, cn } from "@/lib/utils";

function HealthCheckView() {
  const locomotiveId = resolveHealthLocomotiveId();
  const { current, health, loading, fetchFailed } =
    useLocomotiveTelemetryHealth(locomotiveId);

  const event = current?.event;

  const gaugeData = useMemo(
    () => [{ name: "score", value: health.score, fill: gaugeColor(health.score) }],
    [health.score],
  );

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

  const showCriticalRing =
    overspeed;

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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
        <span>
          Локомотив{" "}
          <code className="text-slate-400">{locomotiveId}</code> ·{" "}
          <code className="text-slate-400">/api/locomotives/…/current</code>
        </span>
        {loading && <span className="text-slate-400">Обновление…</span>}
      </div>

      <div className="grid gap-20 lg:grid-cols-2">
        <section
          className={cn(
            "panel relative overflow-hidden lg:col-span-1 h-fit justify-self-end",
            health.category === "Критично" &&
              "animate-critical-pulse border-health-critical/60",
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
                <p
                  className={cn(
                    "mt-2 inline-flex rounded-md px-2 py-1 text-7xl font-semibold uppercase",
                    health.category === "Норма" && "text-emerald-500",
                    health.category === "Внимание" && "text-amber-500",
                    health.category === "Критично" && "text-red-500",
                  )}
                >
                  {health.score}
                </p>
                <p className="text-xs text-secondary">Индекс здоровья</p>
                <p
                  className={cn(
                    "mt-2 inline-flex rounded-full px-3 py-1 text-lg font-semibold tracking-wide",
                    health.category === "Норма" &&
                      "bg-emerald-500/15 text-emerald-500",
                    health.category === "Внимание" &&
                      "bg-amber-500/15 text-amber-500",
                    health.category === "Критично" &&
                      "bg-rose-500/15 text-red-500 ring-1 ring-red-500",
                  )}
                >
                  {health.category}
                </p>
              </div>
            </div>
          </div>
        </section>
        <section className="panel relative overflow-hidden lg:col-span-1 justify-self-start flex items-center justify-center">
          <img src="/images/speed.svg" alt="Speed" className="w-80 h-64 " />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
            <p className="text-6xl font-semibold text-primary mt-10">
              {speedDisplay}
            </p>
            <p className="text-xs text-primary">км/ч</p>
          </div>
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0">
            <p className="text-2xl font-semibold text-primary mt-20">
              {allowedDisplay}
            </p>
          </div>
          {showCriticalRing && (
            <div className="absolute border-[6px] border-red-500 rounded-full w-16 h-16 bottom-0 mb-10" />
          )}
        </section>
      </div>

      <section className="panel">
        <h2 className="text-sm font-medium text-slate-400">
          Телеметрия (wire)
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          JSON из{" "}
          <code className="text-slate-400">GET /api/locomotives/{locomotiveId}/current</code>
          — событие симулятора и активные предупреждения.
        </p>
        <pre className="readout-sm mt-4 max-h-64 overflow-auto rounded-lg bg-black/40 p-4 text-slate-300">
          {JSON.stringify(wirePayload, null, 2)}
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
