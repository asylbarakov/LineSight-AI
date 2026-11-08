import type { CSSProperties } from "react";
export type IconName = "overview" | "video" | "metrics" | "sections" | "preview" | "panel" | "menu" | "close" | "high" | "medium" | "low" | "visibility" | "sparkles" | "send";
const paths: Record<IconName, string> = {
  sparkles: "M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3zM20 2v4M18 4h4",
  send: "M12 20V4m-6 6 6-6 6 6",
  overview: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  video: "M3 5h13v14H3zM16 10l5-4v12l-5-4", metrics: "M4 3v17h17M8 15v-4m5 4V7m5 8V4",
  sections: "M3 4l6 2 6-2 6 2v14l-6-2-6 2-6-2zM9 6v14m6-16v14", preview: "M3 4h18v16H3zM3 9h18M8 9v11",
  panel: "M3 4h18v16H3zM9 4v16M13 9l3 3-3 3", menu: "M4 6h16M4 12h16M4 18h16", close: "M6 6l12 12M6 18L18 6",
  high: "M12 3L2 21h20L12 3zM12 9v5m0 3v.5", medium: "M12 2l10 10-10 10L2 12 12 2zM12 7v6m0 3v.5",
  low: "M5 3h14v18H5zM9 8h6M9 12h6M9 16h3", visibility: "M3 3l18 18M10 5.2c5-1 9 4 11 6.8-1 1.5-2.2 3-3.8 4.2M6.2 6.2C4.4 7.5 3 9.5 2 12c3 5 7 7 11 6.5M10 10a3 3 0 004 4",
};
export function Icon({ name, size = 18, style, className }: { name: IconName; size?: number; style?: CSSProperties; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style} className={className}><path d={paths[name]} /></svg>;
}
