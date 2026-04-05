"use client";

import { differenceInMinutes, formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";
import { AlertTriangle, Flame, Info, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ActiveWarningCurrent } from "@/lib/telemetryApi";

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
    high_vibration: "Двигатель",
    high_brakes_temperature: "Тормоза",
    overspeed: "Скорость",
    upcoming_bad_track: "Путь",
    track_condition_alert: "Путь",
    low_signal_quality: "Навигация",
    voltage_sag: "Контактная сеть",
    high_current: "Электрика",
    low_pressure: "Тормоза",
    low_pneumatic_pressure: "Пневмосистема",
    high_energy_consumption: "Энергия",
    low_fuel: "Топливо",
    weather_condition_alert: "Погода",
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

export type LocomotiveWarningCardItemProps = {
  warning: ActiveWarningCurrent;
  /** Slightly smaller type for fixed toasts on Trends. */
  compact?: boolean;
};

/** One alert card — same markup as the Alerts tab (optionally compact for toasts). */
export function LocomotiveWarningCardItem({ warning: w, compact = false }: LocomotiveWarningCardItemProps) {
  const tier = visualTier(w);
  const cat = categoryLabel(w.rule_id);
  const activeM = activeMinutes(w.first_seen_at);

  const barText = compact ? "text-sm font-normal tracking-wide" : "text-lg font-normal tracking-wide";
  const titleText = compact ? "text-lg font-semibold" : "text-3xl font-semibold";
  const actionText = compact ? "text-sm text-secondary" : "text-2xl text-secondary";
  const catText = compact ? "text-sm font-medium text-secondary sm:mr-4" : "text-3xl font-medium text-secondary sm:mr-10";
  const iconBox = compact ? "h-9 w-9" : "h-12 w-12";
  const flameIcon = compact ? "h-10 w-10" : "h-14 w-14";
  const stdIcon = compact ? "h-9 w-9" : "h-12 w-12";

  if (tier === "critical") {
    return (
      <div className="overflow-hidden rounded-xl border-2 border-red-500 bg-white shadow-lg shadow-black/20">
        <div className={cn("flex items-center justify-between bg-red-500 px-3 py-1.5 text-white sm:px-4 sm:py-2", barText)}>
          <span className="uppercase">КРИТИЧНО</span>
          <span>Активно: {activeM} мин</span>
        </div>
        <div className="flex gap-3 px-3 py-3 sm:gap-4 sm:px-4 sm:py-4">
          <div className={cn("flex shrink-0 items-center justify-center rounded-full text-red-500", iconBox)}>
            <Flame className={flameIcon} aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <p className={cn("text-primary", titleText)}>{w.title}</p>
            <p className={cn("mt-0.5 sm:mt-1", actionText)}>{w.recommended_action}</p>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-secondary/80 sm:mt-3 sm:text-sm">
              <Clock className="h-3.5 w-3.5 shrink-0 sm:h-4 sm:w-4" aria-hidden />
              {formatDistanceToNow(new Date(w.last_seen_at), {
                addSuffix: true,
                locale: ru,
              })}
            </p>
          </div>
          <div className={cn("hidden shrink-0 text-right sm:block", catText)}>{cat}</div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border-2 bg-white shadow-lg shadow-black/20",
        tier === "high" && "border-red-500",
        tier === "medium" && "border-amber-500",
        tier === "info" && "border-sky-500",
      )}
    >
      <div
        className={cn(
          "flex items-center justify-between px-3 py-1.5 text-white sm:px-4 sm:py-2",
          barText,
          tier === "high" && "bg-red-500",
          tier === "medium" && "bg-amber-500",
          tier === "info" && "bg-sky-500",
        )}
      >
        <span className="uppercase">{tierLabel(tier)}</span>
        <span>Активно: {activeM} мин</span>
      </div>

      <div className="flex gap-3 px-3 py-3 sm:gap-4 sm:px-4 sm:py-4">
        <div
          className={cn(
            "flex shrink-0 items-center justify-center rounded-full",
            iconBox,
            tier === "high" && "text-red-500",
            tier === "medium" && "text-amber-500",
            tier === "info" && "text-sky-500",
          )}
        >
          {tier === "info" ? (
            <Info className={stdIcon} aria-hidden />
          ) : tier === "medium" ? (
            <AlertTriangle className={stdIcon} aria-hidden />
          ) : (
            <Flame className={stdIcon} aria-hidden />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p className={cn("text-primary", titleText)}>{w.title}</p>
          <p className={cn("mt-0.5 sm:mt-1", actionText)}>{w.recommended_action}</p>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-secondary/80 sm:mt-3 sm:text-sm">
            <Clock className="h-3.5 w-3.5 shrink-0 sm:h-4 sm:w-4" aria-hidden />
            {formatDistanceToNow(new Date(w.last_seen_at), {
              addSuffix: true,
              locale: ru,
            })}
          </p>
        </div>

        <div className={cn("hidden shrink-0 text-right sm:block", catText)}>{cat}</div>
      </div>
    </div>
  );
}

export type LocomotiveWarningCardsProps = {
  warnings: ActiveWarningCurrent[];
  /** Alerts page: large dashed empty state. Trends: one line or hidden. */
  emptyVariant?: "panel" | "inline" | "hidden";
  locomotiveId?: string;
};

/**
 * Same alert cards as the Alerts tab — reuse on Trends (and anywhere else).
 */
export function LocomotiveWarningCards({
  warnings,
  emptyVariant = "panel",
  locomotiveId,
}: LocomotiveWarningCardsProps) {
  if (warnings.length === 0) {
    if (emptyVariant === "hidden") return null;
    if (emptyVariant === "inline") {
      return (
        <p className="rounded-lg border border-dashed border-slate-300 bg-white/80 px-4 py-3 text-center text-sm text-slate-500">
          Нет активных предупреждений
        </p>
      );
    }
    return (
      <div className="rounded-xl border border-dashed px-6 py-14 text-center text-slate-500">
        Нет активных предупреждений для локомотива{" "}
        <span className="font-mono text-slate-300">{locomotiveId ?? "—"}</span>
      </div>
    );
  }

  return (
    <ul className="space-y-4">
      {warnings.map((w) => (
        <li key={w.warning_id}>
          <LocomotiveWarningCardItem warning={w} />
        </li>
      ))}
    </ul>
  );
}
