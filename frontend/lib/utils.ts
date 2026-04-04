import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSpeed(kmh: number): string {
  return `${kmh.toFixed(1)} km/h`;
}

export function formatTemp(celsius: number): string {
  return `${celsius.toFixed(1)}°C`;
}

export function formatPressure(bar: number): string {
  return `${bar.toFixed(1)} bar`;
}

export function formatFuel(percent: number): string {
  return `${percent.toFixed(1)}%`;
}

export function formatVoltage(v: number): string {
  return `${v.toFixed(1)} V`;
}

export function clampToRange(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function emaSmooth(prev: number, next: number, alpha: number): number {
  return alpha * next + (1 - alpha) * prev;
}
