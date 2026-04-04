const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost";
const API_BASE = RAW_API_URL.replace(/\/+$/, "");
const API_URL = API_BASE.endsWith("/api") ? API_BASE : `${API_BASE}/api`;

export type Loco = { id: string };

export async function getLocomotives() {
  const res = await fetch(`${API_URL}/locomotives`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load locomotives");
  return (await res.json()) as Array<{ id: string; created_at: string; updated_at: string }>;
}

export async function getCurrent(locomotiveId: string) {
  const res = await fetch(`${API_URL}/locomotives/${locomotiveId}/current`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load current snapshot");
  return (await res.json()) as { payload: Record<string, unknown>; last_event_timestamp: string };
}

export async function getLatestMetrics(locomotiveId: string) {
  const res = await fetch(`${API_URL}/locomotives/${locomotiveId}/latest-metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load latest metrics");
  return (await res.json()) as Record<string, unknown>;
}

export async function getSystemMetrics() {
  const res = await fetch(`${API_URL}/system/metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load system metrics");
  return (await res.json()) as Record<string, unknown>;
}

export { API_URL };
