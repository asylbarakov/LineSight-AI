export function scrollToElement(element: Element | null | undefined) {
  let reduce = true;
  try { reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { /* safe immediate scroll */ }
  element?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
}
