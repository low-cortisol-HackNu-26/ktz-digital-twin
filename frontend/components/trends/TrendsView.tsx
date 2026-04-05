"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import {
  fetchLocomotiveCurrent,
  fetchLocomotiveHistory,
  type TelemetryHistoryRow,
} from "@/lib/telemetryApi";
import {
  TREND_WINDOW_MIN,
  brakesTempFromRow,
  currentValue,
  energyOrFuelValue,
  isElectricTraction,
  lastV,
  maxDriveTempFromRow,
  pneumaticValue,
  rowsToPoints,
  voltageValue,
} from "@/lib/telemetryTrendSeries";
import { resolveHealthLocomotiveId } from "@/hooks/useLocomotiveTelemetryHealth";
import {
  thresholdsEnergyAbs,
  thresholdsFuelPercent,
  thresholdsHighIsWorse,
  thresholdsLowIsWorse,
  BRAKES_TEMP_CRIT_C,
  BRAKES_TEMP_WARN_C,
  CURRENT_CRIT_A,
  CURRENT_WARN_A,
  DRIVE_TEMP_CRIT_C,
  DRIVE_TEMP_WARN_C,
  PNEUMATIC_CRIT_BAR,
  PNEUMATIC_WARN_BAR,
  VOLTAGE_CRIT_KV,
  VOLTAGE_WARN_KV,
} from "@/lib/telemetryThresholds";
import { TrendChartCard } from "@/components/trends/TrendChartCard";

const POLL_MS = 4000;
/** Backend cap; need enough rows to cover TREND_WINDOW_MIN at high ingest rate (~10 Hz → 9k points / 15 min). */
const HISTORY_LIMIT = 10_000;

function formatTrendValue(v: number | null, digits: number): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function TrendsView() {
  const locomotiveId = resolveHealthLocomotiveId();
  const [clock, setClock] = useState(() => format(new Date(), "HH:mm"));
  const [history, setHistory] = useState<TelemetryHistoryRow[]>([]);
  const [tractionType, setTractionType] = useState<string | undefined>("electric");
  const [windowEndMs, setWindowEndMs] = useState(() => Date.now());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const tick = useCallback(async () => {
    if (!locomotiveId) {
      setLoading(false);
      setError(true);
      return;
    }
    const now = new Date();
    setWindowEndMs(now.getTime());
    const from = new Date(now.getTime() - TREND_WINDOW_MIN * 60_000);
    const [rows, current] = await Promise.all([
      fetchLocomotiveHistory(locomotiveId, from.toISOString(), now.toISOString(), HISTORY_LIMIT),
      fetchLocomotiveCurrent(locomotiveId),
    ]);
    setHistory(rows);
    const tt = current?.event?.traction_type;
    if (tt) setTractionType(tt);
    setLoading(false);
    setError(rows.length === 0 && current?.event == null);
  }, [locomotiveId]);

  useEffect(() => {
    void tick();
    const poll = window.setInterval(() => void tick(), POLL_MS);
    return () => window.clearInterval(poll);
  }, [tick]);

  useEffect(() => {
    const id = window.setInterval(() => setClock(format(new Date(), "HH:mm")), 1000);
    return () => window.clearInterval(id);
  }, []);

  const electric = isElectricTraction(tractionType);

  const series = useMemo(() => {
    const ptsEnergyFuel = rowsToPoints(history, windowEndMs, TREND_WINDOW_MIN, (r) =>
      energyOrFuelValue(r, isElectricTraction(r.traction_type)),
    );
    const ptsDrive = rowsToPoints(history, windowEndMs, TREND_WINDOW_MIN, maxDriveTempFromRow);
    const ptsBrake = rowsToPoints(history, windowEndMs, TREND_WINDOW_MIN, brakesTempFromRow);
    const ptsPneu = rowsToPoints(history, windowEndMs, TREND_WINDOW_MIN, pneumaticValue);
    const ptsVolt = rowsToPoints(history, windowEndMs, TREND_WINDOW_MIN, voltageValue);
    const ptsCurr = rowsToPoints(history, windowEndMs, TREND_WINDOW_MIN, currentValue);

    return {
      ptsEnergyFuel,
      ptsDrive,
      ptsBrake,
      ptsPneu,
      ptsVolt,
      ptsCurr,
    };
  }, [history, windowEndMs]);

  const cards = useMemo(() => {
    const eStroke = "#a855f7";
    const tempStroke = "#f97316";
    const brakeStroke = "#f87171";
    const pneuStroke = "#3b82f6";
    const voltStroke = "#22c55e";
    const currStroke = "#eab308";

    const energyTitle = electric ? "ПОТРЕБЛЕНИЕ ЭНЕРГИИ" : "ТОПЛИВО";
    const energyUnit = electric ? "кВт·ч" : "%";
    const lvE = lastV(series.ptsEnergyFuel);

    return [
      {
        key: "energy-fuel",
        title: energyTitle,
        unit: energyUnit,
        valueLabel: electric ? formatTrendValue(lvE, 1) : formatTrendValue(lvE, 0),
        points: series.ptsEnergyFuel,
        stroke: eStroke,
        yDomain: electric ? undefined : ([0, 100] as [number, number]),
        yDataBounds: electric ? { min: 0, max: 200 } : { min: 0, max: 100 },
        thresholds: electric ? thresholdsEnergyAbs() : thresholdsFuelPercent(),
      },
      {
        key: "drive",
        title: "ТЕМПЕРАТУРА ДВИГАТЕЛЯ",
        unit: "°C",
        valueLabel: formatTrendValue(lastV(series.ptsDrive), 1),
        points: series.ptsDrive,
        stroke: tempStroke,
        yDataBounds: { min: -20, max: 220 },
        thresholds: thresholdsHighIsWorse(DRIVE_TEMP_WARN_C, DRIVE_TEMP_CRIT_C),
      },
      {
        key: "brake",
        title: "ТЕМПЕРАТУРА ТОРМОЗОВ",
        unit: "°C",
        valueLabel: formatTrendValue(lastV(series.ptsBrake), 1),
        points: series.ptsBrake,
        stroke: brakeStroke,
        yDataBounds: { min: -20, max: 220 },
        thresholds: thresholdsHighIsWorse(BRAKES_TEMP_WARN_C, BRAKES_TEMP_CRIT_C),
      },
      {
        key: "pneu",
        title: "ДАВЛЕНИЕ",
        unit: "bar",
        valueLabel: formatTrendValue(lastV(series.ptsPneu), 1),
        points: series.ptsPneu,
        stroke: pneuStroke,
        yDataBounds: { min: 0, max: 16 },
        thresholds: thresholdsLowIsWorse(PNEUMATIC_WARN_BAR, PNEUMATIC_CRIT_BAR),
      },
      {
        key: "volt",
        title: "НАПРЯЖЕНИЕ",
        unit: "кВ",
        valueLabel: formatTrendValue(lastV(series.ptsVolt), 1),
        points: series.ptsVolt,
        stroke: voltStroke,
        yDataBounds: { min: 0, max: 35 },
        thresholds: thresholdsLowIsWorse(VOLTAGE_WARN_KV, VOLTAGE_CRIT_KV),
      },
      {
        key: "curr",
        title: "ТОК",
        unit: "А",
        valueLabel: formatTrendValue(lastV(series.ptsCurr), 0),
        points: series.ptsCurr,
        stroke: currStroke,
        yDataBounds: { min: 0, max: 5000 },
        thresholds: thresholdsHighIsWorse(CURRENT_WARN_A, CURRENT_CRIT_A),
      },
    ];
  }, [series, electric]);

  return (
    <div className="rounded-2xl p-4 sm:p-5">


      {error && !loading ? (
        <p className="mb-4 rounded-lg border border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-100/90">
          Нет истории в БД за этот интервал — дождитесь симулятора или проверьте ingest.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-4 mt-[-20px]">
        {cards.map((c) => (
          <TrendChartCard
            key={c.key}
            title={c.title}
            unit={c.unit}
            valueLabel={c.valueLabel}
            points={c.points}
            stroke={c.stroke}
            yDomain={c.yDomain}
            yDataBounds={c.yDataBounds}
            thresholds={c.thresholds}
            loading={loading}
          />
        ))}
      </div>
    </div>
  );
}

export default TrendsView;
