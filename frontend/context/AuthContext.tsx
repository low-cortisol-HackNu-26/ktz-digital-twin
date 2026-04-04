"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { DriverInfo } from "@/lib/types";
import {
  clearStoredSession,
  fetchDriverProfile,
  loginWithPassword,
  logoutRemote,
  readStoredSession,
  refreshAccessToken,
  type StoredSession,
} from "@/lib/authClient";
import { useMockDashboardStore } from "@/store/mockDashboardStore";

type AuthContextValue = {
  ready: boolean;
  driver: DriverInfo | null;
  session: StoredSession | null;
  signIn: (uid: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function applyLocomotive(driver: DriverInfo | null) {
  const id = driver?.locomotive_id?.trim();
  useMockDashboardStore.getState().setLocomotiveId(id && id.length ? id : "LK-42");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<StoredSession | null>(null);
  const [driver, setDriver] = useState<DriverInfo | null>(null);

  const refreshProfile = useCallback(async () => {
    const profile = await fetchDriverProfile();
    if (profile) {
      setDriver(profile);
      applyLocomotive(profile);
      const stored = readStoredSession();
      if (stored) setSession({ ...stored, driver: profile });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = readStoredSession();
      if (!stored) {
        if (!cancelled) {
          setSession(null);
          setDriver(null);
          setReady(true);
        }
        return;
      }
      const next =
        stored.expiresAt - 60_000 <= Date.now()
          ? await refreshAccessToken()
          : stored;
      if (cancelled) return;
      if (!next) {
        setSession(null);
        setDriver(null);
        setReady(true);
        return;
      }
      setSession(next);
      setDriver(next.driver);
      applyLocomotive(next.driver);
      const profile = await fetchDriverProfile();
      if (!cancelled && profile) {
        setDriver(profile);
        applyLocomotive(profile);
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!session) return;
    const id = window.setInterval(() => {
      void refreshAccessToken().then((next) => {
        if (next) setSession(next);
        else {
          clearStoredSession();
          setSession(null);
          setDriver(null);
          applyLocomotive(null);
        }
      });
    }, 4 * 60_000);
    return () => window.clearInterval(id);
  }, [session?.accessToken]);

  const signIn = useCallback(async (uid: string, password: string) => {
    const next = await loginWithPassword(uid, password);
    setSession(next);
    setDriver(next.driver);
    applyLocomotive(next.driver);
    await refreshProfile();
  }, [refreshProfile]);

  const signOut = useCallback(async () => {
    await logoutRemote();
    setSession(null);
    setDriver(null);
    applyLocomotive(null);
  }, []);

  const value = useMemo(
    () => ({
      ready,
      driver,
      session,
      signIn,
      signOut,
      refreshProfile,
    }),
    [ready, driver, session, signIn, signOut, refreshProfile],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
