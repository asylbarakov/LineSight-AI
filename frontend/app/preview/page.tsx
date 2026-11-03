"use client";

import { useState } from "react";
import { MockBadge } from "@/components/Badges";

// Макеты направлений развития: статичные данные, ничего не считается (по плану MVP).
const TABS = ["Обзор", "Карта участка", "Сравнение облётов", "Model Lab"] as const;
type Tab = (typeof TABS)[number];

const KPI = [
  ["Инспекций за месяц", "18"],
  ["Находок высокого приоритета", "7"],
  ["Км обследовано", "126"],
  ["Среднее время отчёта", "6 мин"],
];

export default function PreviewPage() {
  const [tab, setTab] = useState<Tab>("Обзор");
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Направления развития</h1>
        <MockBadge />
      </div>
      <p className="max-w-2xl text-sm text-muted">
        Эти экраны показывают, куда может развиваться система. Данные на них вымышленные и не относятся к реальным инспекциям.
      </p>
      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm ${
              tab === t ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Обзор" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {KPI.map(([k, v]) => (
            <div key={k} className="rounded-xl border border-line bg-surface p-5">
              <div className="text-xs uppercase tracking-wide text-muted">{k}</div>
              <div className="mt-2 text-3xl font-semibold">{v}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "Карта участка" && (
        <div className="rounded-xl border border-line bg-surface p-5">
          <svg viewBox="0 0 640 280" className="w-full" role="img" aria-label="Схема участка ЛЭП с находками">
            <rect width="640" height="280" rx="12" fill="var(--surface-2)" />
            <path d="M30 220 C150 150 220 190 320 120 S520 90 610 40" stroke="var(--accent)" strokeWidth="3" fill="none" />
            {[[90, 192], [180, 168], [280, 138], [380, 112], [480, 94], [570, 58]].map(([x, y], i) => (
              <g key={i}>
                <circle cx={x} cy={y} r="6" fill="var(--bg)" stroke="var(--fg)" strokeWidth="2" />
                <text x={x - 6} y={y + 22} fontSize="11" fill="var(--muted)">{`Оп. ${i + 1}`}</text>
              </g>
            ))}
            <circle cx="280" cy="138" r="12" fill="none" stroke="var(--danger)" strokeWidth="2" />
            <circle cx="480" cy="94" r="12" fill="none" stroke="var(--warn)" strokeWidth="2" />
          </svg>
          <p className="mt-3 text-sm text-muted">Привязка находок к GPS-трекам дрона — после приёмки.</p>
        </div>
      )}

      {tab === "Сравнение облётов" && (
        <div className="grid gap-4 md:grid-cols-2">
          {["Облёт от 12.10", "Облёт от 03.11"].map((t, i) => (
            <div key={t} className="rounded-xl border border-line bg-surface p-5">
              <div className="mb-3 text-sm font-medium">{t}</div>
              <div className="flex aspect-video items-center justify-center rounded-lg bg-surface2 text-xs text-muted">кадр опоры №3</div>
              <p className="mt-3 text-sm text-muted">{i === 0 ? "Изолятор без видимых повреждений" : "Новая трещина на изоляторе"}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "Model Lab" && (
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
              <tr><th className="px-5 py-3 font-medium">Модель</th><th className="px-5 py-3 text-right font-medium">mAP50</th><th className="px-5 py-3 text-right font-medium">FPS</th></tr>
            </thead>
            <tbody>
              {[["yolov8n (базовая)", "0.62", "48"], ["yolov8s (дообученная)", "0.71", "31"]].map(([m, a, f]) => (
                <tr key={m} className="border-b border-line/60 last:border-0">
                  <td className="px-5 py-3">{m}</td><td className="px-5 py-3 text-right tabular-nums">{a}</td><td className="px-5 py-3 text-right tabular-nums">{f}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
