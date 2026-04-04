import type { DriverInfo, RefreshResponse, SessionResponse } from "@/lib/types";

const STORAGE_KEY = "ktz_session_v1";

export type StoredSession = {
  accessToken: string;
  refreshToken: string;
  /** Unix ms — access token expiry from API */
  expiresAt: number;
  driver: DriverInfo;
};

export function getApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

export function readStoredSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

export function writeStoredSession(session: StoredSession): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

/** Revokes server session (POST /api/auth/logout) then clears local storage. */
export async function logoutRemote(): Promise<void> {
  try {
    const token = await getValidAccessToken();
    if (token) {
      await fetch(`${getApiBase()}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } catch {
    /* still clear locally */
  } finally {
    clearStoredSession();
  }
}

function sessionFromLogin(data: SessionResponse): StoredSession {
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: data.expires_at,
    driver: data.driver,
  };
}

function sessionFromRefresh(
  prev: StoredSession,
  data: RefreshResponse,
): StoredSession {
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt: data.expires_at,
    driver: data.driver,
  };
}

export async function loginWithPassword(
  uid: string,
  password: string,
): Promise<StoredSession> {
  const res = await fetch(`${getApiBase()}/api/auth/card`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid, password }),
  });
  const data = (await res.json().catch(() => ({}))) as SessionResponse & {
    detail?: string | { msg?: string }[];
  };
  if (!res.ok) {
    const msg =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).filter(Boolean).join(", ")
          : "Sign-in failed";
    throw new Error(msg || "Sign-in failed");
  }
  const session = sessionFromLogin(data);
  writeStoredSession(session);
  return session;
}

let refreshPromise: Promise<StoredSession | null> | null = null;

export async function refreshAccessToken(): Promise<StoredSession | null> {
  if (refreshPromise) return refreshPromise;
  const current = readStoredSession();
  if (!current?.refreshToken) return null;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      });
      const body = (await res.json().catch(() => ({}))) as RefreshResponse & {
        detail?: string;
      };
      if (!res.ok) {
        clearStoredSession();
        return null;
      }
      const next = sessionFromRefresh(current, body);
      writeStoredSession(next);
      return next;
    } catch {
      clearStoredSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/** Returns a usable access token, refreshing when close to expiry. */
export async function getValidAccessToken(): Promise<string | null> {
  const s = readStoredSession();
  if (!s) return null;
  const bufferMs = 60_000;
  if (s.expiresAt - bufferMs <= Date.now()) {
    const next = await refreshAccessToken();
    return next?.accessToken ?? null;
  }
  return s.accessToken;
}

export async function fetchDriverProfile(): Promise<DriverInfo | null> {
  const token = await getValidAccessToken();
  if (!token) return null;
  const res = await fetch(`${getApiBase()}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const retried = await refreshAccessToken();
    if (!retried) return null;
    const retry = await fetch(`${getApiBase()}/api/auth/me`, {
      headers: { Authorization: `Bearer ${retried.accessToken}` },
    });
    if (!retry.ok) return null;
    return (await retry.json()) as DriverInfo;
  }
  return (await res.json()) as DriverInfo;
}
