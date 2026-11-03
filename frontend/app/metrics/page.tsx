"use client";

import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/Badges";
import { useToast } from "@/components/Toast";
import { getMetrics } from "@/lib/api";
import { fmtPercent } from "@/lib/format";
import type { Metrics } from "@/lib/types";

const STAGES = ["decode", "detect", "track", "findings", "db"] as const;
const STAGE_RU: Record<(typeof STAGES)[number], string> = {
  decode: "Декодирование",
  detect: "Детекция",
  track: "Трекинг",
  findings: "Находки",
  db: "Запись в БД",
};

export default function MetricsPage() {
  const toast = useToast();
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    getMetrics().then(setM).catch((e) => toast(e.message ?? "Не удалось загрузить метрики"));
  }, [toast]);

  const cards = m
    ? [
        ["Инспекций", String(m.inspections_total)],
        ["Среднее время обработки", m.avg_processing_sec != null ? `${m.avg_processing_sec.toFixed(1)} с` : "—"],
        ["Средний FPS", m.avg_fps != null ? m.avg_fps.toFixed(1) : "—"],
        ["Доля ошибок", fmtPercent(m.failed_share)],
      ]
    : [];

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold tracking-tight">Метрики</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {m === null && [0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-24" />)}
        {cards.map(([k, v]) => (
          <div key={k} className="rounded-xl border border-line bg-surface p-5">
            <div className="text-xs uppercase tracking-wide text-muted">{k}</div>
            <div className="mt-2 text-3xl font-semibold tabular-nums">{v}</div>
          </div>
        ))}
      </div>
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-5 py-3 font-medium">Запуск</th>
              <th className="px-5 py-3 font-medium">Статус</th>
              <th className="px-5 py-3 text-right font-medium">FPS</th>
              {STAGES.map((s) => (
                <th key={s} className="px-3 py-3 text-right font-medium">{STAGE_RU[s]}, с</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {m?.recent_runs.map((r) => (
              <tr key={r.id} className="border-b border-line/60 last:border-0">
                <td className="px-5 py-3 font-medium">{r.title}</td>
                <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                <td className="px-5 py-3 text-right tabular-nums">{r.fps?.toFixed(1) ?? "—"}</td>
                {STAGES.map((s) => (
                  <td key={s} className="px-3 py-3 text-right tabular-nums text-muted">
                    {r.stage_times?.[s] != null ? r.stage_times[s].toFixed(1) : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {m && m.recent_runs.length === 0 && <p className="px-5 py-10 text-center text-sm text-muted">Запусков пока нет</p>}
      </div>
    </div>
  );
}
