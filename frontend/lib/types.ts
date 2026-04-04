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

export type HealthCategory = "Норма" | "Внимание" | "Критично";

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

/** Backend `DriverInfo` (GET /api/auth/me). */
export type DriverInfo = {
  id: string;
  company_id: string;
  name: string;
  role: "Machinist" | "Dispatcher" | "Admin";
  locomotive_id: string | null;
};

/** Backend `SessionResponse` (POST /api/auth/card). */
export type SessionResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: number;
  session_id: string;
  driver: DriverInfo;
};

/** Backend `RefreshResponse` (POST /api/auth/refresh). */
export type RefreshResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: number;
  driver: DriverInfo;
};
