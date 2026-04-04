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
import { cn } from "@/lib/utils";

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
  
  const gaugeTrackColor =
    health.category === "Критично"
      ? "rgba(255,255,255,0.9)"
      : health.category === "Внимание"
        ? "rgba(255,255,255,0.9)"
        : "rgba(255,255,255,0.92)";

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2 ">
        <section
          className={cn(
            "w-full relative overflow-hidden col-span-1 bg-slate-100/40 rounded-lg h-80",
            health.category === "Критично" &&
              "animate-critical-pulse border-health-critical/60",
            health.category === "Внимание" && "border-health-warning/50",
            health.category === "Норма" && "border-health-normal/30",
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
              </div>
          
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
