"use client";

import dynamic from "next/dynamic";

const HealthCheckView = dynamic(() => import("@/components/health/HealthCheckView"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-[50vh] items-center justify-center text-slate-500">
      Loading dashboard…
    </div>
  ),
});

export default function HealthPage() {
  return <HealthCheckView />;
}
