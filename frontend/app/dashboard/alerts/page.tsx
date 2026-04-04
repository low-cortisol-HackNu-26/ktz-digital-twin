"use client";

import dynamic from "next/dynamic";

const TrendAlertsView = dynamic(() => import("@/components/alerts/TrendAlertsView"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-[50vh] items-center justify-center text-slate-500">
      Loading alerts…
    </div>
  ),
});

export default function AlertsPage() {
  return <TrendAlertsView />;
}
