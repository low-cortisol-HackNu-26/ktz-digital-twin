import { create } from "zustand";
import type {
  AlertLogEntry,
  HealthCategory,
  HealthIndex,
  TelemetryPacket,
  TrendPoint,
} from "@/lib/types";
import { clampToRange, emaSmooth } from "@/lib/utils";

const MAX_HISTORY = 120;
const LOC_ID = "LK-42";

/** Demo route near Almaty (approximate corridor for map polyline). */
export const ROUTE_LINE: [number, number][] = [
  [43.222, 76.851],
  [43.238, 76.892],
];

function isoNow(): string {
  return new Date().toISOString();
}

function computeHealth(packet: TelemetryPacket): HealthIndex {
  const speedOk = clampToRange(packet.speed / 120, 0, 1);
  const tempStress = clampToRange((packet.temp_engine - 75) / 40, 0, 1);
  const brakeOk = clampToRange(packet.pressure_brake / 8, 0, 1);
  const voltOk = clampToRange((packet.voltage - 20) / 8, 0, 1);
  const fuelOk = clampToRange(packet.fuel / 100, 0, 1);

  let score =
    speedOk * 22 +
    (1 - tempStress) * 28 +
    brakeOk * 18 +
    voltOk * 12 +
    fuelOk * 10;
  score -= packet.alert_codes.length * 12;
  score = clampToRange(Math.round(score), 0, 100);

  let category: HealthCategory = "Норма";
  if (score < 45) category = "Критично";
  else if (score < 72) category = "Внимание";

  const candidates: string[] = [];
  if (tempStress > 0.45)
    candidates.push(`Engine temp +${Math.round(tempStress * 100)}% vs band`);
  if (packet.pressure_brake < 4.5) candidates.push("Brake pressure low");
  if (packet.voltage < 22) candidates.push("Electrical bus undervoltage");
  if (packet.fuel < 25) candidates.push("Fuel reserve margin thin");
  if (packet.speed > 105) candidates.push("Speed envelope high");
  if (packet.alert_codes.length)
    candidates.push(`Active alerts: ${packet.alert_codes.join(", ")}`);
  const padding = [
    "GPS track stable",
    "Traction inverter nominal",
    "Driver vigilance link OK",
    "Consist integrity OK",
  ];
  for (const line of padding) {
    if (candidates.length >= 5) break;
    if (!candidates.includes(line)) candidates.push(line);
  }
  if (candidates.length === 0) candidates.push("Telemetry within nominal band");

  return {
    score,
    category,
    factors: candidates.slice(0, 5),
    timestamp: packet.timestamp,
  };
}

type DashboardState = {
  connected: boolean;
  /** Simulated client→server latency (ms) for UI demo */
  simulatedLatencyMs: number;
  receivedAt: string | null;
  packet: TelemetryPacket;
  smoothed: Pick<
    TelemetryPacket,
    "temp_engine" | "pressure_brake" | "voltage"
  >;
  health: HealthIndex;
  history: TrendPoint[];
  alertLog: AlertLogEntry[];
  routeProgress: number;
  /** EMA state */
  _ema: { temp: number; pressure: number; voltage: number };
  advance: () => void;
  setConnected: (v: boolean) => void;
  setLocomotiveId: (locomotiveId: string) => void;
};

function initialPacket(): TelemetryPacket {
  return {
    locomotive_id: LOC_ID,
    speed: 72,
    fuel: 68,
    temp_engine: 88,
    pressure_brake: 6.1,
    voltage: 24.4,
    alert_codes: [],
    timestamp: isoNow(),
  };
}

export const useMockDashboardStore = create<DashboardState>((set, get) => {
  const first = initialPacket();
  const health = computeHealth(first);
  return {
    connected: true,
    simulatedLatencyMs: 38,
    receivedAt: isoNow(),
    packet: first,
    smoothed: {
      temp_engine: first.temp_engine,
      pressure_brake: first.pressure_brake,
      voltage: first.voltage,
    },
    health,
    history: [
      {
        t: Date.now(),
        speed: first.speed,
        temp_engine: first.temp_engine,
        pressure_brake: first.pressure_brake,
        voltage: first.voltage,
      },
    ],
    alertLog: [],
    routeProgress: 0.35,
    _ema: {
      temp: first.temp_engine,
      pressure: first.pressure_brake,
      voltage: first.voltage,
    },
    setConnected: (v) => set({ connected: v }),
    setLocomotiveId: (locomotiveId) =>
      set((state) => ({
        packet: { ...state.packet, locomotive_id: locomotiveId },
      })),
    advance: () => {
      const s = get();
      if (!s.connected) return;

      const spike = Math.random() < 0.08;
      const speedDelta = (Math.random() - 0.45) * 6 + (spike ? 18 : 0);
      let speed = clampToRange(s.packet.speed + speedDelta, 0, 118);
      const fuel = clampToRange(s.packet.fuel - Math.random() * 0.12, 8, 100);
      let temp = clampToRange(
        s.packet.temp_engine + (Math.random() - 0.4) * 2 + (spike ? 9 : 0),
        65,
        108,
      );
      let pressure = clampToRange(
        s.packet.pressure_brake + (Math.random() - 0.5) * 0.35 - (spike ? 1.2 : 0),
        2.5,
        8.5,
      );
      let voltage = clampToRange(
        s.packet.voltage + (Math.random() - 0.5) * 0.25 - (spike ? 1.1 : 0),
        20,
        28,
      );

      const alpha = 0.35;
      const eTemp = emaSmooth(s._ema.temp, temp, alpha);
      const ePressure = emaSmooth(s._ema.pressure, pressure, alpha);
      const eVoltage = emaSmooth(s._ema.voltage, voltage, alpha);

      const alert_codes: string[] = [];
      if (temp > 98) alert_codes.push("E012");
      if (pressure < 4.2) alert_codes.push("B044");
      if (voltage < 22) alert_codes.push("V201");
      if (speed > 102) alert_codes.push("S009");

      const timestamp = isoNow();
      const raw: TelemetryPacket = {
        locomotive_id: s.packet.locomotive_id,
        speed,
        fuel,
        temp_engine: temp,
        pressure_brake: pressure,
        voltage,
        alert_codes,
        timestamp,
      };

      const displayPacket: TelemetryPacket = {
        ...raw,
        temp_engine: eTemp,
        pressure_brake: ePressure,
        voltage: eVoltage,
      };

      const health = computeHealth(displayPacket);
      const t = Date.now();
      const history = [
        ...s.history.slice(-(MAX_HISTORY - 1)),
        {
          t,
          speed: displayPacket.speed,
          temp_engine: displayPacket.temp_engine,
          pressure_brake: displayPacket.pressure_brake,
          voltage: displayPacket.voltage,
        },
      ];

      let alertLog = s.alertLog;
      if (alert_codes.length) {
        const newEntries: AlertLogEntry[] = alert_codes.map((code, i) => ({
          id: `${t}-${i}-${code}`,
          code,
          message:
            code === "E012"
              ? "Engine temperature excursion"
              : code === "B044"
                ? "Brake manifold pressure low"
                : code === "V201"
                  ? "Traction bus voltage drop"
                  : "Operational envelope advisory",
          time: timestamp,
          severity: health.category,
        }));
        alertLog = [...newEntries, ...alertLog].slice(0, 80);
      }

      const routeProgress =
        (s.routeProgress + (displayPacket.speed / 360000) * 50) % 1;

      set({
        packet: displayPacket,
        smoothed: {
          temp_engine: eTemp,
          pressure_brake: ePressure,
          voltage: eVoltage,
        },
        _ema: { temp: eTemp, pressure: ePressure, voltage: eVoltage },
        health,
        history,
        alertLog,
        receivedAt: isoNow(),
        routeProgress,
      });
    },
  };
});

export function positionAlongRoute(progress: number): [number, number] {
  const p = progress % 1;
  const n = ROUTE_LINE.length - 1;
  const f = p * n;
  const i = Math.floor(f);
  const j = Math.min(i + 1, n);
  const u = f - i;
  const a = ROUTE_LINE[i];
  const b = ROUTE_LINE[j];
  return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u];
}
