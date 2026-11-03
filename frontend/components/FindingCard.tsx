"use client";

import { frameUrl } from "@/lib/api";
import { fmtPercent, fmtTimecode, frameName } from "@/lib/format";
import { typeRu } from "@/lib/texts";
import type { Decision, Finding } from "@/lib/types";
import { FindingStatusBadge, PriorityBadge } from "./Badges";
import { KeyFrame } from "./KeyFrame";

interface Props {
  inspectionId: string;
  finding: Finding;
  busy?: boolean;
  onSeek: (sec: number) => void;
  onDecide: (id: string, status: Decision) => void;
}

const ACTIONS: { status: Decision; label: string; cls: string }[] = [
  { status: "confirmed", label: "Подтвердить", cls: "border-ok/40 text-ok hover:bg-ok/10" },
  { status: "rejected", label: "Отклонить", cls: "border-danger/40 text-danger hover:bg-danger/10" },
  { status: "reshoot", label: "Переснять", cls: "border-warn/40 text-warn hover:bg-warn/10" },
];

export function FindingCard({ inspectionId, finding: f, busy, onSeek, onDecide }: Props) {
  const src = f.frame_path ? frameUrl(inspectionId, frameName(f.frame_path)) : null;
  return (
    <article className="rounded-xl border border-line bg-surface p-4" data-testid="finding-card">
      <div className="flex flex-wrap items-center gap-2">
        <PriorityBadge priority={f.priority} />
        <FindingStatusBadge status={f.status} />
        <span className="ml-auto text-xs text-muted">Уверенность {fmtPercent(f.confidence)}</span>
      </div>
      <h3 className="mt-2 text-sm font-semibold">{typeRu(f.type)}</h3>
      <button
        type="button"
        onClick={() => onSeek(f.timecode_sec)}
        className="mt-1 text-sm text-accent hover:underline"
        title="Перейти к этому моменту в видео"
      >
        ▶ {fmtTimecode(f.timecode_sec)}
      </button>
      <KeyFrame src={src} bbox={f.bbox} alt={typeRu(f.type)} className="mt-3 w-full" />
      {f.type === "low_visibility" && (
        <p className="mt-2 text-xs text-muted">Участок снят нечётко, рекомендуется повторная съёмка.</p>
      )}
      <div className="mt-3 grid grid-cols-3 gap-2">
        {ACTIONS.map((a) => (
          <button
            key={a.status}
            type="button"
            disabled={busy}
            onClick={() => onDecide(f.id, a.status)}
            className={`rounded-md border px-2 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${a.cls} ${
              f.status === a.status ? "bg-surface2" : ""
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
    </article>
  );
}
