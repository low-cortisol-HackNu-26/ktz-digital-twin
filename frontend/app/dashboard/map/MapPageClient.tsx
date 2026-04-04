"use client";

import dynamic from "next/dynamic";

const RailwayMap = dynamic(() => import("@/components/map/RailwayMap"), {
  ssr: false,
  loading: () => (
    <section className="panel flex h-[min(640px,calc(100vh-220px))] items-center justify-center text-slate-500">
      Loading map…
    </section>
  ),
});

export default function MapPageClient() {
  return <RailwayMap />;
}
