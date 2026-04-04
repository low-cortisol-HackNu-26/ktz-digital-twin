"use client";

import { useCallback, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { shouldSuppressDashboardSpaceCycle } from "@/lib/kiosk";

/** Order: Health → Alerts → Trends → Map (Space cycles forward). */
export const DASHBOARD_TAB_PATHS = [
  "/dashboard/health",
  "/dashboard/alerts",
  "/dashboard/trends",
  "/dashboard/map",
] as const;

export function useDashboardSpaceCycle() {
  const pathname = usePathname();
  const router = useRouter();

  const cycleTab = useCallback(() => {
    const i = DASHBOARD_TAB_PATHS.indexOf(pathname as (typeof DASHBOARD_TAB_PATHS)[number]);
    const current = i >= 0 ? i : 0;
    const next = (current + 1) % DASHBOARD_TAB_PATHS.length;
    router.push(DASHBOARD_TAB_PATHS[next]);
  }, [pathname, router]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      if (shouldSuppressDashboardSpaceCycle(e.target)) return;
      e.preventDefault();
      cycleTab();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [cycleTab]);
}
