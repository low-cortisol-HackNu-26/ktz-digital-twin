"use client";

import { useEffect } from "react";
import { useMockDashboardStore } from "@/store/mockDashboardStore";

/** Advances the in-browser simulator at ~1 Hz (stand-in for WebSocket feed). */
export function MockTelemetryTicker() {
  const advance = useMockDashboardStore((s) => s.advance);

  useEffect(() => {
    const id = window.setInterval(() => advance(), 1000);
    return () => window.clearInterval(id);
  }, [advance]);

  return null;
}
