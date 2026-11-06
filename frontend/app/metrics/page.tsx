"use client";

import Link from "next/link";
import { StatusBadge } from "@/components/Badges";
import { useResource } from "@/components/useResource";
import { ResourceError } from "@/components/ResourceError";
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
  const { data: m, loading, error, retry } = useResource<Metrics>(getMetrics);

  const cards = m
    ? [
        ["Среднее время обработки", m.avg_processing_sec != null ? `${m.avg_processing_sec.toFixed(1)} с` : "—"],
        ["Средний FPS", m.avg_fps != null ? m.avg_fps.toFixed(1) : "—"],
        ["Доля ошибок", fmtPercent(m.failed_share)],
      ]
    : [];

  return (
    <div className="space-y-8">
      <div><h1 className="page-title">Технические метрики</h1><p className="mt-2 text-base text-muted">Скорость обработки видео и длительность этапов ML.</p></div>{error && <ResourceError error={error} loading={loading} onRetry={retry} />}
      <div className="grid gap-4 border-y border-line py-5 sm:grid-cols-3">
        {m === null && !error && [0, 1, 2].map((i) => <div key={i} className="skeleton h-24" />)}
        {cards.map(([k, v]) => (
          <div key={k} className="min-w-0 sm:border-l sm:border-line sm:pl-5 sm:first:border-0 sm:first:pl-0">
            <div className="text-label text-muted">{k}</div>
            <div className="mt-2 text-readout font-medium tabular-nums">{v}</div>
          </div>
        ))}
      </div>
      <section><h2 className="mb-4 section-title">Время по этапам</h2><div className="overflow-x-auto">
        <table className="w-full min-w-[850px] text-base"><caption className="sr-only">Длительность этапов последних запусков, в секундах</caption>
          <thead className="border-b border-line text-left text-label text-muted">
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
                <td className="px-5 py-3 font-medium"><Link href={`/inspections/${r.id}`} className="text-accent hover:underline">{r.title}</Link>{r.error_code && <p className="mt-1 text-xs text-danger">{r.error_code}</p>}</td>
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
        {m && m.recent_runs.length === 0 && <p className="px-5 py-10 text-center text-base text-muted">Запусков пока нет</p>}
        {!m && error && <p className="px-5 py-10 text-base text-muted">Длительность этапов недоступна.</p>}
      </div></section>
    </div>
  );
}
