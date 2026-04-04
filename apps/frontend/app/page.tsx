"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { API_URL, getCurrent, getLocomotives, getSystemMetrics } from "../lib/api";
import { useTelemetryStore } from "../store/telemetryStore";

const EMPTY_SERIES: Array<{ t: number; v: number }> = [];

function fmt(value: unknown, unit = "", digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(digits)}${unit}`;
}

function TinyChart({ values, min = 0, max = 1 }: { values: Array<{ t: number; v: number }>; min?: number; max?: number }) {
  if (!values.length) {
    return <div className="h-20 rounded bg-panel/60" />;
  }

  const points = values
    .map((p, i) => {
      const x = (i / Math.max(values.length - 1, 1)) * 100;
      const y = 100 - ((p.v - min) / Math.max(max - min, 1e-6)) * 100;
      return `${x},${Math.max(0, Math.min(100, y))}`;
    })
    .join(" ");

  return (
    <svg viewBox="0 0 100 100" className="h-20 w-full rounded bg-panel/60">
      <polyline fill="none" stroke="#35C4A8" strokeWidth="2" points={points} />
    </svg>
  );
}

export default function MonitorPage() {
  const telemetryState = useTelemetryStore();
  const {
    selectedLocomotive,
    setSelectedLocomotive,
    setConnectionStatus,
    seedSnapshot,
    pushTelemetry,
    speed: speedByLocomotive,
    power: powerByLocomotive,
    brake: brakeByLocomotive,
    temp: tempByLocomotive,
    connectionStatus,
    lastUpdate,
    latest: latestByLocomotive,
  } = telemetryState;

  const latest = latestByLocomotive[selectedLocomotive];

  const speedSeries = speedByLocomotive[selectedLocomotive] ?? EMPTY_SERIES;
  const powerSeries = powerByLocomotive[selectedLocomotive] ?? EMPTY_SERIES;
  const brakeSeries = brakeByLocomotive[selectedLocomotive] ?? EMPTY_SERIES;
  const tempSeries = tempByLocomotive[selectedLocomotive] ?? EMPTY_SERIES;

  const locomotives = useQuery({ queryKey: ["locomotives"], queryFn: getLocomotives, refetchInterval: 10000 });
  const systemMetrics = useQuery({ queryKey: ["system-metrics"], queryFn: getSystemMetrics, refetchInterval: 2000 });

  useEffect(() => {
    if (!selectedLocomotive && locomotives.data?.[0]?.id) {
      setSelectedLocomotive(locomotives.data[0].id);
    }
  }, [locomotives.data, selectedLocomotive, setSelectedLocomotive]);

  useEffect(() => {
    if (!selectedLocomotive) return;
    getCurrent(selectedLocomotive)
      .then((snapshot) => {
        seedSnapshot(selectedLocomotive, snapshot.payload as any);
      })
      .catch(() => null);
  }, [selectedLocomotive, seedSnapshot]);

  useEffect(() => {
    setConnectionStatus("connecting");
    const ws = new WebSocket(`${(process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost/ws")}/telemetry`);

    ws.onopen = () => {
      setConnectionStatus("connected");
      if (selectedLocomotive) {
        ws.send(JSON.stringify({ action: "subscribe", locomotive_id: selectedLocomotive }));
      }
    };

    ws.onclose = () => setConnectionStatus("disconnected");
    ws.onerror = () => setConnectionStatus("disconnected");

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "telemetry" && msg.locomotive_id && msg.payload) {
        pushTelemetry(msg.locomotive_id, msg.payload);
      }
    };

    return () => ws.close();
  }, [pushTelemetry, selectedLocomotive, setConnectionStatus]);

  const kpis = useMemo(
    () => [
      ["Speed", fmt(latest?.speed_kph, " kph", 1)],
      ["Allowed", fmt(latest?.allowed_speed_kph, " kph", 1)],
      ["Traction Power", fmt(latest?.traction_power_kw, " kW", 0)],
      ["Brake Pipe", fmt(latest?.brake_pipe_pressure_bar, " bar", 2)],
      ["Catenary", fmt(latest?.catenary_voltage_kv, " kV", 2)],
      ["Motor Temp", fmt(latest?.traction_motor_temp_c, " C", 1)],
      ["Gearbox Vib", fmt(latest?.vibration_gearbox, " mm/s", 2)],
      ["Signal Quality", fmt(latest?.signal_quality, "", 3)],
    ],
    [latest]
  );

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 md:p-8">
      <header className="card p-4">
        <h1 className="text-2xl font-semibold">KZ8A Live Telemetry Monitor</h1>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-300">
          <div>API: {API_URL}</div>
          <div>WS: {connectionStatus}</div>
          <div>Last update: {lastUpdate ? new Date(lastUpdate).toLocaleTimeString() : "-"}</div>
          <div>Ingest rate: {fmt(systemMetrics.data?.ingest_rate_per_sec, " ev/s", 2)}</div>
        </div>
        <div className="mt-3">
          <label className="text-sm">Locomotive</label>
          <select
            className="ml-2 rounded border border-line bg-bg px-2 py-1"
            value={selectedLocomotive}
            onChange={(e) => setSelectedLocomotive(e.target.value)}
          >
            {(locomotives.data ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.id}
              </option>
            ))}
          </select>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {kpis.map(([label, value]) => (
          <div key={label} className="card p-3">
            <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
            <div className="mt-2 text-2xl font-semibold text-accent">{value}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="card p-3">
          <div className="mb-2 text-sm text-slate-300">Speed</div>
          <TinyChart values={speedSeries} min={0} max={180} />
        </div>
        <div className="card p-3">
          <div className="mb-2 text-sm text-slate-300">Traction Power</div>
          <TinyChart values={powerSeries} min={0} max={9000} />
        </div>
        <div className="card p-3">
          <div className="mb-2 text-sm text-slate-300">Brake Pressure</div>
          <TinyChart values={brakeSeries} min={0} max={8} />
        </div>
        <div className="card p-3">
          <div className="mb-2 text-sm text-slate-300">Temperatures (motor)</div>
          <TinyChart values={tempSeries} min={0} max={220} />
        </div>
      </section>
    </main>
  );
}
