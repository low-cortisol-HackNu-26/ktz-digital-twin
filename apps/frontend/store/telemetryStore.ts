import { create } from "zustand";

type Point = { t: number; v: number };

export type TelemetryPayload = {
  timestamp: string;
  locomotive_id: string;
  speed_kph?: number | null;
  allowed_speed_kph?: number | null;
  traction_power_kw?: number | null;
  brake_pipe_pressure_bar?: number | null;
  catenary_voltage_kv?: number | null;
  traction_motor_temp_c?: number | null;
  converter_temp_c?: number | null;
  transformer_temp_c?: number | null;
  vibration_gearbox?: number | null;
  signal_quality?: number | null;
};

type State = {
  selectedLocomotive: string;
  connectionStatus: "disconnected" | "connecting" | "connected";
  lastUpdate: number | null;
  latest: Record<string, TelemetryPayload>;
  speed: Record<string, Point[]>;
  power: Record<string, Point[]>;
  brake: Record<string, Point[]>;
  temp: Record<string, Point[]>;
  setSelectedLocomotive: (id: string) => void;
  setConnectionStatus: (status: State["connectionStatus"]) => void;
  seedSnapshot: (id: string, payload: TelemetryPayload) => void;
  pushTelemetry: (id: string, payload: TelemetryPayload) => void;
};

const MAX_POINTS = 120;

function pushPoint(arr: Point[] | undefined, point: Point) {
  const next = arr ? [...arr, point] : [point];
  if (next.length > MAX_POINTS) next.splice(0, next.length - MAX_POINTS);
  return next;
}

export const useTelemetryStore = create<State>((set) => ({
  selectedLocomotive: "",
  connectionStatus: "disconnected",
  lastUpdate: null,
  latest: {},
  speed: {},
  power: {},
  brake: {},
  temp: {},
  setSelectedLocomotive: (id) => set({ selectedLocomotive: id }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  seedSnapshot: (id, payload) =>
    set((state) => ({
      latest: { ...state.latest, [id]: payload }
    })),
  pushTelemetry: (id, payload) =>
    set((state) => {
      const t = Date.now();
      return {
        lastUpdate: t,
        latest: { ...state.latest, [id]: payload },
        speed: {
          ...state.speed,
          [id]: pushPoint(state.speed[id], { t, v: Number(payload.speed_kph ?? 0) })
        },
        power: {
          ...state.power,
          [id]: pushPoint(state.power[id], { t, v: Number(payload.traction_power_kw ?? 0) })
        },
        brake: {
          ...state.brake,
          [id]: pushPoint(state.brake[id], { t, v: Number(payload.brake_pipe_pressure_bar ?? 0) })
        },
        temp: {
          ...state.temp,
          [id]: pushPoint(state.temp[id], { t, v: Number(payload.traction_motor_temp_c ?? 0) })
        }
      };
    })
}));
