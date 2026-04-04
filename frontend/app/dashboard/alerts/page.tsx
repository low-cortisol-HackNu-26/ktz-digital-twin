"use client";

import { LocomotiveWarningsView } from "@/components/locomotive/LocomotiveWarningsView";
import { DEFAULT_TELEMETRY_LOCOMOTIVE_ID } from "@/lib/telemetryApi";

export default function AlertsPage() {
  return <LocomotiveWarningsView locomotiveId={DEFAULT_TELEMETRY_LOCOMOTIVE_ID} />;
}
