"use client";

import { frameUrl } from "@/lib/api";
import { fmtPercent, frameName } from "@/lib/format";
import { findingTimecode } from "@/lib/timeline";
import { typeRu } from "@/lib/texts";
import type { Decision, Finding } from "@/lib/types";
import { FindingStatusBadge, PriorityBadge } from "./Badges";
import { KeyFrame } from "./KeyFrame";

interface Props {
  inspectionId: string;
  finding: Finding;
  busy?: boolean;
  selected?: boolean;
  error?: string;
  onSelect?: (finding: Finding) => void;
  onRetry?: () => void;
  onSeek: (sec: number) => void;
  onDecide: (id: string, status: Decision) => void;
}

const ACTIONS: { status: Decision; label: string; cls: string }[] = [
  { status: "confirmed", label: "Подтвердить", cls: "border-control text-fg hover:bg-surface2" },
  { status: "rejected", label: "Отклонить", cls: "border-line text-muted hover:bg-surface2" },
  { status: "reshoot", label: "Переснять", cls: "border-line text-muted hover:bg-surface2" },
];

export function FindingCard({ inspectionId, finding: f, busy, selected, error, onSelect, onRetry, onSeek, onDecide }: Props) {
  const src = f.frame_path ? frameUrl(inspectionId, frameName(f.frame_path)) : null;
  return (
    <article className={`finding-card rounded-md border-l-2 px-3 py-3 transition-colors ${selected ? "border-accent bg-accent-soft/35" : "border-transparent hover:bg-surface2/40"} ${onSelect ? "cursor-pointer" : ""}`}
      data-testid="finding-card" data-finding-id={f.id} data-selected={selected ? "true" : "false"}
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest("button, a, input, select, textarea, summary, [role='dialog']")) onSelect?.(f);
      }}>
      <p className="mb-1 text-xs text-muted">{f.status !== "new" ? "Решение инженера" : f.type === "low_visibility" || f.priority === "insufficient_data" ? "Качество съёмки · На проверке" : "Предположение модели · На проверке"}</p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <PriorityBadge priority={f.priority} />
        <FindingStatusBadge status={f.status} />
        <span className="text-xs text-muted">Уверенность {fmtPercent(f.confidence)}</span>
      </div>
      <button
        type="button"
        onClick={() => onSelect ? onSelect(f) : onSeek(f.timecode_sec)}
        aria-pressed={!!selected}
        aria-label={`${typeRu(f.type)}, перейти к ${findingTimecode(f.timecode_sec)}`}
        className="mt-2 flex min-h-11 w-full items-center justify-between gap-3 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-accent"
        title="Перейти к этому моменту в видео"
      >
        <span className="block text-base font-medium">{typeRu(f.type)}</span>
        <span className="shrink-0 text-sm tabular-nums text-accent">{findingTimecode(f.timecode_sec)} <span aria-hidden="true">↗</span></span>
      </button>
      <details className="mt-1">
        <summary className="min-h-11 cursor-pointer rounded text-label leading-[44px] text-muted">Ключевой кадр</summary>
        <KeyFrame src={src} bbox={f.bbox} alt={typeRu(f.type)} className="mt-1 w-full" />
      </details>
      <div className="finding-actions mt-2">
        {ACTIONS.map((a) => (
          <button
            key={a.status}
            type="button"
            disabled={busy || f.status === a.status}
            aria-pressed={f.status === a.status}
            onClick={() => onDecide(f.id, a.status)}
            className={`min-h-11 rounded-md border px-2 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${a.cls} ${
              f.status === a.status ? "bg-surface2" : ""
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      {busy && <p role="status" className="mt-2 text-xs text-muted">Сохраняем решение…</p>}
      {error && <div className="mt-3 text-xs text-danger" role="alert">
        <p>{error}</p>
        {onRetry && <button type="button" onClick={onRetry} disabled={busy}
          className="btn mt-2">Повторить сохранение</button>}
      </div>}
    </article>
  );
}
