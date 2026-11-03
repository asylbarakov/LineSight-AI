import type { BBox } from "./types";

/** 73.4 → "01:13" */
export function fmtTimecode(sec: number): string {
  const total = Math.max(0, Math.floor(sec));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Рамка в долях 0–1 → CSS-проценты (работает при любом размере кадра). */
export function bboxToStyle(b: BBox): { left: string; top: string; width: string; height: string } {
  const pct = (v: number) => `${(Math.min(1, Math.max(0, v)) * 100).toFixed(2)}%`;
  return { left: pct(b.x), top: pct(b.y), width: pct(b.w), height: pct(b.h) };
}

/** Рамка в долях → пиксели изображения заданного размера. */
export function bboxToPixels(b: BBox, width: number, height: number) {
  return {
    x: Math.round(b.x * width),
    y: Math.round(b.y * height),
    w: Math.round(b.w * width),
    h: Math.round(b.h * height),
  };
}

export function fmtPercent(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function fmtSeconds(v: number | null | undefined, digits = 1): string {
  return v == null ? "—" : `${v.toFixed(digits)} с`;
}

/** "frames/lv_1.jpg" → "lv_1.jpg" */
export function frameName(path: string): string {
  return path.split("/").pop() ?? path;
}
