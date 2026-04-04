"use client";

import dynamic from "next/dynamic";

const TrendsView = dynamic(() => import("@/components/trends/TrendsView"), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-[50vh] items-center justify-center text-slate-500">
      Loading charts…
    </div>
  ),
});

export default function TrendsPage() {
  return <TrendsView />;
}
