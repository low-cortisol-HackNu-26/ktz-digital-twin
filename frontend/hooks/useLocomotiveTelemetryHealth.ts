"use client";

import { useEffect, useMemo, useState } from "react";
import { computeHealthFromLocomotiveCurrent } from "@/lib/healthFromTelemetry";
import {
  DEFAULT_TELEMETRY_LOCOMOTIVE_ID,
  fetchLocomotiveCurrent,
  type LocomotiveCurrentResponse,
} from "@/lib/telemetryApi";
import type { HealthIndex } from "@/lib/types";

const POLL_MS = 1000;

export type LocomotiveTelemetryHealthState = {
  locomotiveId: string;
  current: LocomotiveCurrentResponse | null;
  health: HealthIndex;
  loading: boolean;
  /** True after first completed request that returned null (network/HTTP error). */
  fetchFailed: boolean;
};

export function resolveHealthLocomotiveId(): string {
  return (
    process.env.NEXT_PUBLIC_MAP_LOCOMOTIVE_ID?.trim() || DEFAULT_TELEMETRY_LOCOMOTIVE_ID
  );
}

export function useLocomotiveTelemetryHealth(
  locomotiveId: string,
): LocomotiveTelemetryHealthState {
  const [current, setCurrent] = useState<LocomotiveCurrentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchFailed, setFetchFailed] = useState(false);

  useEffect(() => {
    if (!locomotiveId) {
      setLoading(false);
      setFetchFailed(true);
      setCurrent(null);
      return;
    }

    let cancelled = false;

    async function tick() {
      const data = await fetchLocomotiveCurrent(locomotiveId);
      if (cancelled) return;
      setCurrent(data);
      setLoading(false);
      if (data === null) setFetchFailed(true);
      else setFetchFailed(false);
    }

    void tick();
    const id = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [locomotiveId]);

  const health = useMemo(() => computeHealthFromLocomotiveCurrent(current), [current]);

  return {
    locomotiveId,
    current,
    health,
    loading,
    fetchFailed,
  };
}
