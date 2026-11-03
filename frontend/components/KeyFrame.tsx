"use client";

import { useState } from "react";
import { bboxToStyle } from "@/lib/format";
import type { BBox } from "@/lib/types";

interface Props {
  src: string | null;
  bbox: BBox | null;
  alt: string;
  className?: string;
}

/** Ключевой кадр с рамкой поверх (позиция в процентах — работает при любом размере окна). Клик — увеличить. */
export function KeyFrame({ src, bbox, alt, className = "" }: Props) {
  const [zoom, setZoom] = useState(false);
  const [broken, setBroken] = useState(false);

  if (!src || broken) {
    return (
      <div className={`flex items-center justify-center rounded-lg border border-dashed border-line bg-surface2 text-xs text-muted ${className}`}>
        {src ? "Кадр недоступен" : "Без ключевого кадра"}
      </div>
    );
  }

  const frame = (
    <div className="relative inline-block w-full">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="block w-full rounded-lg" onError={() => setBroken(true)} />
      {bbox && (
        <div
          data-testid="bbox"
          className="pointer-events-none absolute rounded-sm border-2 border-danger shadow-[0_0_0_1px_rgba(0,0,0,0.5)]"
          style={bboxToStyle(bbox)}
        />
      )}
    </div>
  );

  return (
    <>
      <button type="button" onClick={() => setZoom(true)} className={`block cursor-zoom-in text-left ${className}`} aria-label="Увеличить кадр">
        {frame}
      </button>
      {zoom && (
        <div
          className="fixed inset-0 z-50 flex cursor-zoom-out items-center justify-center bg-black/80 p-6"
          onClick={() => setZoom(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="max-h-full w-full max-w-5xl">{frame}</div>
        </div>
      )}
    </>
  );
}
