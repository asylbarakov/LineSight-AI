"use client";

import { useEffect, useRef, useState } from "react";
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
  const closeButton = useRef<HTMLButtonElement>(null);
  const frameViewport = useRef<HTMLDivElement>(null);
  useEffect(() => { setBroken(false); setZoom(false); }, [src]);

  useEffect(() => {
    if (!zoom || broken || !src) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setZoom(false);
      if (event.key === "Tab") {
        const first = closeButton.current, last = frameViewport.current;
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [zoom, broken, src]);

  if (!src || broken) {
    return (
      <div className={`flex min-h-20 items-center justify-center gap-3 rounded-lg border border-dashed border-line bg-surface2 px-3 py-4 text-xs text-muted ${className}`}>
        {src ? "Кадр недоступен" : "Без ключевого кадра"}
        {src && <button type="button" onClick={() => setBroken(false)} className="btn">Повторить</button>}
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
          className="pointer-events-none absolute rounded-sm border-2 border-danger shadow-[0_0_0_1px_rgb(var(--media-outline-rgb))]"
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
          className="fixed inset-0 z-50 flex cursor-zoom-out items-center justify-center bg-overlay/80 p-4 sm:p-6"
          onClick={event => { if (event.target === event.currentTarget) setZoom(false); }}
          role="dialog"
          aria-modal="true"
          aria-label={alt}
        >
          <div className="flex max-h-[calc(100svh-3rem)] w-full max-w-5xl cursor-default flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-xl">
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-line px-3 py-2"><p className="min-w-0 break-words text-sm font-medium text-fg">{alt}</p>
              <button ref={closeButton} type="button" onClick={() => setZoom(false)}
                className="btn">Закрыть</button></div>
            <div ref={frameViewport} className="min-h-0 overflow-auto overscroll-contain p-3" tabIndex={0} role="region" aria-label="Увеличенный ключевой кадр">{frame}</div>
          </div>
        </div>
      )}
    </>
  );
}
