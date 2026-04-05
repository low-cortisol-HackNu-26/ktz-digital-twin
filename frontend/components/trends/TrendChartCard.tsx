"use client";

import { useId, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";
import type { TrendPoint } from "@/lib/telemetryTrendSeries";
import { yDomainForTrends } from "@/lib/telemetryThresholds";
import { cn } from "@/lib/utils";

export type ThresholdLine = { y: number; stroke: string; strokeDasharray?: string };

type TrendChartCardProps = {
  title: string;
  unit: string;
  valueLabel: string;
  points: TrendPoint[];
  stroke: string;
  yDomain?: [number | string, number | string];
  /** When computing Y extent, ignore samples outside this range (bad units / spikes). */
  yDataBounds?: { min: number; max: number };
  thresholds?: ThresholdLine[];
  loading?: boolean;
};

function formatYTick(v: number): string {
  if (!Number.isFinite(v)) return "";
  const a = Math.abs(v);
  if (a >= 1000) return v.toFixed(0);
  if (a >= 100) return v.toFixed(1);
  if (a >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

const X_TICKS = [-15, -12, -9, -6, -3, 0];

export function TrendChartCard({
  title,
  unit,
  valueLabel,
  points,
  stroke,
  yDomain,
  yDataBounds,
  thresholds = [],
  loading,
}: TrendChartCardProps) {
  const gid = useId().replace(/:/g, "");
  const data = useMemo(() => points.map((p) => ({ m: p.m, v: Number(p.v) })), [points]);

  const yDomainResolved = useMemo((): [number, number] => {
    const merged = yDomainForTrends(data.map((d) => d.v), thresholds, {
      dataBounds: yDataBounds,
      padRatio: 0.08,
    });
    if (
      yDomain != null &&
      typeof yDomain[0] === "number" &&
      typeof yDomain[1] === "number"
    ) {
      const lo = yDomain[0];
      const hi = yDomain[1];
      return [Math.min(lo, merged[0]), Math.max(hi, merged[1])];
    }
    return merged;
  }, [data, thresholds, yDomain, yDataBounds]);

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-xl bg-white p-4 shadow-lg shadow-black/10 ring-1 ring-slate-200/80",
      )}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <h3 className="text-xl font-bold uppercase tracking-wide text-slate-500">
          {title}
        </h3>
        <div className="text-right">
          <span className="text-2xl font-bold tabular-nums text-slate-800">{valueLabel}</span>
          <span className="ml-1 text-sm font-semibold text-slate-600">{unit}</span>
        </div>
      </div>
      <div className="min-h-[140px] flex-1">
        {loading ? (
          <div className="flex h-[160px] items-center justify-center text-xs text-slate-400">
            Загрузка…
          </div>
        ) : data.length === 0 ? (
          <div className="flex h-[160px] items-center justify-center text-xs text-slate-400">
            Нет точек за выбранный интервал
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart
              data={data}
              margin={{ top: 10, right: 10, left: 6, bottom: 14 }}
            >
              <defs>
                <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={stroke} stopOpacity={0.45} />
                  <stop offset="100%" stopColor={stroke} stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                type="number"
                dataKey="m"
                domain={[-15, 0]}
                ticks={X_TICKS}
                tick={{ fontSize: 14, fill: "#64748b" }}
                tickMargin={10}
                tickFormatter={(v) => (v === 0 ? "0" : `${v}m`)}
                axisLine={{ stroke: "#cbd5e1" }}
              />
              <YAxis
                type="number"
                width={56}
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickMargin={10}
                axisLine={false}
                tickLine={false}
                domain={yDomainResolved}
                tickCount={5}
                allowDecimals
                tickFormatter={formatYTick}
              />
              <Tooltip
                contentStyle={{
                  background: "#fff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelFormatter={(m) => (m === 0 ? "Сейчас" : `${Number(m).toFixed(1)} мин`)}
                formatter={(v: number) => [Number(v).toFixed(2), ""]}
              />
              {thresholds.map((t, i) => (
                <ReferenceLine
                  key={i}
                  y={t.y}
                  stroke={t.stroke}
                  strokeDasharray={t.strokeDasharray ?? "5 5"}
                  strokeWidth={1.5}
                />
              ))}
              <Area
                type="monotone"
                dataKey="v"
                stroke={stroke}
                strokeWidth={2}
                fill={`url(#${gid})`}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
