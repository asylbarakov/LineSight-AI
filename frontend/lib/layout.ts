/** A saved user choice wins; compact navigation is only a first-visit laptop default. */
export function initialSidebarCollapsed(saved: string | null, width: number) {
  if (saved === "true" || saved === "false") return saved === "true";
  return width >= 1024 && width < 1280;
}
