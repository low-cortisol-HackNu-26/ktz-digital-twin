const STORAGE_KEY = "ktz_dispatcher_session_v1";

export type DriverInfo = {
  id: string;
  company_id: string;
  name: string;
  role: string;
  locomotive_id?: string | null;
};

export type StoredSession = {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  driver: DriverInfo;
};

export function getDispatcherApiBase(): string {
  return (process.env.NEXT_PUBLIC_DISPATCHER_API_URL ?? "http://localhost:8002").replace(/\/$/, "");
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

export async function loginDispatcher(uid: string, password: string): Promise<StoredSession> {
  const res = await fetch(`${getDispatcherApiBase()}/api/auth/card`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid, password }),
  });
  const data = (await res.json().catch(() => ({}))) as {
    access_token?: string;
    refresh_token?: string;
    expires_at?: number;
    driver?: DriverInfo;
    detail?: string;
  };
  if (!res.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Вход не выполнен");
  }
  const session: StoredSession = {
    accessToken: data.access_token!,
    refreshToken: data.refresh_token!,
    expiresAt: data.expires_at!,
    driver: data.driver!,
  };
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
      const res = await fetch(`${getDispatcherApiBase()}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      });
      const body = (await res.json().catch(() => ({}))) as {
        access_token?: string;
        refresh_token?: string;
        expires_at?: number;
        driver?: DriverInfo;
      };
      if (!res.ok) {
        clearStoredSession();
        return null;
      }
      const next: StoredSession = {
        accessToken: body.access_token!,
        refreshToken: body.refresh_token!,
        expiresAt: body.expires_at!,
        driver: body.driver ?? current.driver,
      };
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

export async function logoutDispatcher(): Promise<void> {
  try {
    const token = await getValidAccessToken();
    if (token) {
      await fetch(`${getDispatcherApiBase()}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } catch {
    /* ignore */
  } finally {
    clearStoredSession();
  }
}
