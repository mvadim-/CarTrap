export function shouldUseMobileFullscreen(enabled = true): boolean {
  if (!enabled || typeof window === "undefined") {
    return false;
  }
  const hasCoarsePointer =
    typeof window.matchMedia === "function" ? window.matchMedia("(pointer: coarse)").matches : "ontouchstart" in window;
  return hasCoarsePointer && window.innerWidth <= 900;
}
