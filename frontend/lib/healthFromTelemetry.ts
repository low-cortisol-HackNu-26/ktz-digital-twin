import type { ActiveWarningCurrent, LocomotiveCurrentResponse } from "@/lib/telemetryApi";
import type { HealthCategory, HealthIndex } from "@/lib/types";
import { clampToRange } from "@/lib/utils";

function categoryFromScore(score: number): HealthCategory {
  if (score < 45) return "Критично";
  if (score < 72) return "Внимание";
  return "Норма";
}

function warningPenalty(w: ActiveWarningCurrent): number {
  if (!w.active) return 0;
  const sev = w.severity?.toLowerCase() ?? "";
  if (sev === "critical") return 14;
  if (sev === "warning" || sev === "warn") return 7;
  return 4;
}

/**
 * Derives a 0–100 health index from simulator `event` + `active_warnings`
 * (same locomotive as map: GET /api/locomotives/{id}/current).
 */
export function computeHealthFromLocomotiveCurrent(
  response: LocomotiveCurrentResponse | null,
): HealthIndex {
  const isoFallback = new Date().toISOString();

  if (!response) {
    return {
      score: 0,
      category: "Критично",
      factors: ["Нет связи с API телеметрии"],
      timestamp: isoFallback,
    };
  }

  const ev = response.event;
  if (!ev) {
    return {
      score: 55,
      category: "Внимание",
      factors: ["Телеметрия для локомотива ещё не поступила"],
      timestamp: isoFallback,
    };
  }

  const allowed =
    typeof ev.allowed_speed_kph === "number" && ev.allowed_speed_kph > 0
      ? ev.allowed_speed_kph
      : 120;
  const speed = typeof ev.speed_kph === "number" ? ev.speed_kph : 0;
  const speedOk =
    speed > allowed ? clampToRange(allowed / speed, 0, 1) : 1;

  const temps = [
    ev.transformer_temp_c,
    ev.converter_temp_c,
    ev.traction_motor_temp_c,
    ev.axle_bearing_temp_c,
  ].filter((n): n is number => typeof n === "number");
  const maxTemp = temps.length ? Math.max(...temps) : 45;
  const tempStress = clampToRange((maxTemp - 75) / 45, 0, 1);

  const brakePipe = typeof ev.brake_pipe_pressure_bar === "number" ? ev.brake_pipe_pressure_bar : 0;
  const brakeOk = clampToRange(brakePipe / 8, 0, 1);

  const kv = typeof ev.catenary_voltage_kv === "number" ? ev.catenary_voltage_kv : 25;
  const voltOk = clampToRange((kv - 15) / 14, 0, 1);

  const dq = typeof ev.data_quality === "number" ? ev.data_quality : 1;
  const sq = typeof ev.signal_quality === "number" ? ev.signal_quality : 1;
  const linkOk = clampToRange((dq + sq) / 2, 0, 1);

  let score =
    speedOk * 22 +
    (1 - tempStress) * 26 +
    brakeOk * 16 +
    voltOk * 14 +
    linkOk * 12;

  const faults = ev.active_fault_codes?.length ?? 0;
  score -= faults * 12;

  for (const w of response.active_warnings ?? []) {
    score -= warningPenalty(w);
  }

  score = clampToRange(Math.round(score), 0, 100);
  const category = categoryFromScore(score);

  const candidates: string[] = [];
  if (speed > allowed && allowed > 0) {
    candidates.push(`Превышение: ${speed.toFixed(0)} км/ч при допуске ${allowed.toFixed(0)}`);
  }
  if (tempStress > 0.45) {
    candidates.push(`Температурный запас снижен (макс. ${maxTemp.toFixed(0)}°C)`);
  }
  if (brakePipe > 0 && brakePipe < 4) {
    candidates.push("Низкое давление в тормозной магистрали");
  }
  if (kv < 18) {
    candidates.push(`Низкое напряжение КС: ${kv.toFixed(1)} кВ`);
  }
  if (faults > 0) {
    candidates.push(`Коды неисправностей: ${ev.active_fault_codes!.join(", ")}`);
  }
  for (const w of response.active_warnings ?? []) {
    if (w.active && w.title && !candidates.includes(w.title)) {
      candidates.push(w.title);
    }
  }
  if (candidates.length === 0) {
    candidates.push("Показатели в допустимых пределах");
  }

  return {
    score,
    category,
    factors: candidates.slice(0, 6),
    timestamp: ev.timestamp || ev.ingestion_time || isoFallback,
  };
}
