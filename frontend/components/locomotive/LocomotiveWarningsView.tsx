"use client";

import { useCallback, useEffect, useState } from "react";
import { type ActiveWarningCurrent, fetchActiveWarningsViaCurrent } from "@/lib/telemetryApi";
import { LocomotiveWarningCards } from "@/components/locomotive/LocomotiveWarningCards";

export function LocomotiveWarningsView({ locomotiveId }: { locomotiveId: string }) {
  const [warnings, setWarnings] = useState<ActiveWarningCurrent[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const list = await fetchActiveWarningsViaCurrent(locomotiveId);
    setWarnings(Array.isArray(list) ? list : []);
    setLoading(false);
  }, [locomotiveId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-slate-500">
        Загрузка предупреждений…
      </div>
    );
  }

  return (
    <LocomotiveWarningCards
      warnings={warnings}
      emptyVariant="panel"
      locomotiveId={locomotiveId}
    />
  );
}
