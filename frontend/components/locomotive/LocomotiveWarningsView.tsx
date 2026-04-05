"use client";

import { useCallback, useEffect, useState } from "react";
import { differenceInMinutes, formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { AlertTriangle, Flame, Info, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { type ActiveWarningCurrent, fetchActiveWarningsViaCurrent } from "@/lib/telemetryApi";

type VisualTier = "critical" | "high" | "medium" | "info";

function visualTier(w: ActiveWarningCurrent): VisualTier {
  if (w.severity === "critical") return "critical";
  if (w.severity === "info") return "info";
  if (["low_signal_quality", "upcoming_bad_track"].includes(w.rule_id)) return "info";
  if (w.rule_id === "high_temperature") return "medium";
  return "high";
}

function categoryLabel(ruleId: string): string {
  const map: Record<string, string> = {
    high_temperature: "Двигатель",
    overspeed: "Скорость",
    upcoming_bad_track: "Путь",
    low_signal_quality: "Навигация",
    voltage_sag: "Контактная сеть",
    high_vibration: "Двигатель",
  };
  return map[ruleId] ?? "Система";
}

function tierLabel(tier: VisualTier): string {
  switch (tier) {
    case "critical":
      return "КРИТИЧНО";
    case "high":
      return "ВНИМАНИЕ";
    case "medium":
      return "СРЕДНЕ";
    case "info":
      return "ИНФО";
    default:
      return "";
  }
}

function activeMinutes(firstSeenAt: string): number {
  return Math.max(0, differenceInMinutes(new Date(), new Date(firstSeenAt)));
}

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

  if (warnings.length === 0) {
    return (
      <div className="rounded-xl border border-dashed px-6 py-14 text-center text-slate-500">
        Нет активных предупреждений для локомотива{" "}
        <span className="font-mono text-slate-300">{locomotiveId}</span>
      </div>
    );
  }

  return (
    <ul className="space-y-4">
      {warnings.map((w) => {
        const tier = visualTier(w);
        const cat = categoryLabel(w.rule_id);
        const activeM = activeMinutes(w.first_seen_at);

        return (
          <li key={w.warning_id}>
            {tier === "critical" ? (
              <div className="overflow-hidden rounded-xl border border-red-500 border-2 shadow-lg shadow-black/20">
                <div className="flex items-center justify-between bg-red-500 px-4 py-2 text-lg font-normal  tracking-wide text-white">
                  <span className="uppercase">КРИТИЧНО</span>
                  <span>Активно: {activeM} мин</span>
                </div>
                <div className="flex gap-4  px-4 py-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-red-500">
                    <Flame className="h-14 w-14" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-3xl font-semibold text-primary">{w.title}</p>
                    <p className="mt-1 text-2xl text-secondary">{w.recommended_action}</p>
                    <p className="mt-3 flex items-center gap-1.5 text-sm text-secondary/80">
        <Clock className="h-4 w-4 shrink-0" aria-hidden />
        {formatDistanceToNow(new Date(w.last_seen_at), {
          addSuffix: true,
          locale: ru,
        })}
      </p>
                  </div>
                  <div className="hidden shrink-0 text-right mr-10 text-3xl font-medium text-secondary sm:block">
                    {cat}
                  </div>
                </div>
              </div>
            ) : (
              <div
  className={cn(
    "overflow-hidden rounded-xl border-2 shadow-lg shadow-black/20",
    tier === "high" && "border-red-500",
    tier === "medium" && "border-amber-500",
    tier === "info" && "border-sky-500",
  )}
>
  <div
    className={cn(
      "flex items-center justify-between px-4 py-2 text-lg font-normal tracking-wide text-white",
      tier === "high" && "bg-red-500",
      tier === "medium" && "bg-amber-500",
      tier === "info" && "bg-sky-500",
    )}
  >
    <span className="uppercase">{tierLabel(tier)}</span>
    <span>Активно: {activeM} мин</span>
  </div>

  <div className="flex gap-4 px-4 py-4">
    <div
      className={cn(
        "flex h-12 w-12 shrink-0 items-center justify-center rounded-full",
        tier === "high" && "text-red-500",
        tier === "medium" && "text-amber-500",
        tier === "info" && "text-sky-500",
      )}
    >
      {tier === "info" ? (
        <Info className="h-12 w-12" aria-hidden />
      ) : tier === "medium" ? (
        <AlertTriangle className="h-12 w-12" aria-hidden />
      ) : (
        <Flame className="h-12 w-12" aria-hidden />
      )}
    </div>

    <div className="min-w-0 flex-1">
      <p className="text-3xl font-semibold text-primary">{w.title}</p>
      <p className="mt-1 text-2xl text-secondary">{w.recommended_action}</p>
      <p className="mt-3 flex items-center gap-1.5 text-sm text-secondary/80">
        <Clock className="h-4 w-4 shrink-0" aria-hidden />
        {formatDistanceToNow(new Date(w.last_seen_at), {
          addSuffix: true,
          locale: ru,
        })}
      </p>
    </div>

    <div className="hidden shrink-0 mr-10 text-right text-3xl font-medium text-secondary sm:block">
      {cat}
    </div>
  </div>
</div>

            )}
          </li>
        );
      })}
    </ul>
  );
}
