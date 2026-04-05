"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { format } from "date-fns";
import {
  fetchActiveWarningsViaCurrent,
  fetchLocomotiveCurrent,
  fetchLocomotiveHistory,
  type ActiveWarningCurrent,
  type TelemetryHistoryRow,
} from "@/lib/telemetryApi";
import { LocomotiveWarningCardItem } from "@/components/locomotive/LocomotiveWarningCards";
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
/** How long a new-alert toast stays fixed on top of the Trends view. */
const TREND_NEW_ALERT_MS = 5000;
/** Backend cap; need enough rows to cover TREND_WINDOW_MIN at high ingest rate (~10 Hz → 9k points / 15 min). */
const HISTORY_LIMIT = 10_000;

type TrendToastEntry = { key: string; warning: ActiveWarningCurrent };

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
  const [newAlertToasts, setNewAlertToasts] = useState<TrendToastEntry[]>([]);

  const knownWarningIdsRef = useRef<Set<string>>(new Set());
  const warningsSeededRef = useRef(false);
  const toastTimeoutsRef = useRef<ReturnType<typeof globalThis.setTimeout>[]>([]);

  const pushNewAlertToast = useCallback((w: ActiveWarningCurrent) => {
    const key = `${w.warning_id}-${Date.now()}`;
    setNewAlertToasts((prev) => [...prev, { key, warning: w }]);
    const tid = globalThis.setTimeout(() => {
      setNewAlertToasts((prev) => prev.filter((t) => t.key !== key));
      toastTimeoutsRef.current = toastTimeoutsRef.current.filter((x) => x !== tid);
    }, TREND_NEW_ALERT_MS);
    toastTimeoutsRef.current.push(tid);
  }, []);

  useEffect(() => {
    knownWarningIdsRef.current = new Set();
    warningsSeededRef.current = false;
    setNewAlertToasts([]);
    toastTimeoutsRef.current.forEach(clearTimeout);
    toastTimeoutsRef.current = [];
  }, [locomotiveId]);

  useEffect(
    () => () => {
      toastTimeoutsRef.current.forEach(clearTimeout);
    },
    [],
  );

  const tick = useCallback(async () => {
    if (!locomotiveId) {
      setLoading(false);
      setError(true);
      return;
    }
    const now = new Date();
    setWindowEndMs(now.getTime());
    const from = new Date(now.getTime() - TREND_WINDOW_MIN * 60_000);
    const [rows, current, activeWarnings] = await Promise.all([
      fetchLocomotiveHistory(locomotiveId, from.toISOString(), now.toISOString(), HISTORY_LIMIT),
      fetchLocomotiveCurrent(locomotiveId),
      fetchActiveWarningsViaCurrent(locomotiveId),
    ]);
    setHistory(rows);

    const list = Array.isArray(activeWarnings) ? activeWarnings : [];
    const ids = new Set(list.map((w) => w.warning_id));
    if (!warningsSeededRef.current) {
      knownWarningIdsRef.current = ids;
      warningsSeededRef.current = true;
    } else {
      const prev = knownWarningIdsRef.current;
      for (const w of list) {
        if (!prev.has(w.warning_id)) pushNewAlertToast(w);
      }
      knownWarningIdsRef.current = ids;
    }

    const tt = current?.event?.traction_type;
    if (tt) setTractionType(tt);
    setLoading(false);
    setError(rows.length === 0 && current?.event == null);
  }, [locomotiveId, pushNewAlertToast]);

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
    <div className="relative rounded-2xl p-4 sm:p-5 mt-[-20px]">
      <div  
        className="pointer-events-none fixed left-0 right-0 top-4 z-[90] flex flex-col items-center gap-3 px-3 sm:top-6"
        aria-live="assertive"
        aria-relevant="additions"
      >
        {newAlertToasts.map(({ key, warning }) => (
          <div
            key={key}
            className="pointer-events-auto w-full max-w-lg origin-top animate-trend-toast-in shadow-2xl"
          >
            <LocomotiveWarningCardItem warning={warning} compact />
          </div>
        ))}
      </div>

      {error && !loading ? (
        <p className="mb-4 rounded-lg border border-amber-900/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-100/90">
          Нет истории в БД за этот интервал — дождитесь симулятора или проверьте ingest.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-4">
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
