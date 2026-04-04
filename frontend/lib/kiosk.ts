/** True when Space should not cycle dashboard tabs (typing in a field, etc.). */
export function shouldSuppressDashboardSpaceCycle(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  if (el.closest("[data-kiosk-input]")) return true;
  return false;
}
