/** Mirrors the hackathon telemetry packet (snake_case as on the wire). */
export type TelemetryPacket = {
  locomotive_id: string;
  speed: number;
  fuel: number;
  temp_engine: number;
  pressure_brake: number;
  voltage: number;
  alert_codes: string[];
  timestamp: string;
};

export type HealthCategory = "NORMAL" | "WARNING" | "CRITICAL";

export type HealthIndex = {
  score: number;
  category: HealthCategory;
  factors: string[];
  timestamp: string;
};

export type TrendPoint = {
  t: number;
  speed: number;
  temp_engine: number;
  pressure_brake: number;
  voltage: number;
};

export type AlertLogEntry = {
  id: string;
  code: string;
  message: string;
  time: string;
  severity: HealthCategory;
};
