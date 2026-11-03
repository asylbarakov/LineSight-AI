"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { StatusBadge } from "@/components/Badges";
import { FindingCard } from "@/components/FindingCard";
import { useToast } from "@/components/Toast";
import { ApiError, downloadReport, getFindings, getInspection, patchFinding, videoUrl } from "@/lib/api";
import { fmtDate, fmtTimecode } from "@/lib/format";
import { errorText } from "@/lib/texts";
import type { Decision, Finding, FindingStatus, InspectionDetail } from "@/lib/types";

type Filter = "all" | FindingStatus;
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "Все" },
  { key: "new", label: "Новые" },
  { key: "confirmed", label: "Подтверждённые" },
  { key: "rejected", label: "Отклонённые" },
  { key: "reshoot", label: "Переснять" },
];

export default function InspectionPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const video = useRef<HTMLVideoElement>(null);
  const [insp, setInsp] = useState<InspectionDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);

  // опрос статуса каждые 2 секунды, пока не done / failed
  const status = insp?.status;
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const d = await getInspection(id);
        if (!alive) return;
        setInsp(d);
        if (d.status === "queued" || d.status === "processing") timer = setTimeout(tick, 2000);
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else timer = setTimeout(tick, 4000);
      }
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [id]);

  useEffect(() => {
    if (status !== "done") return;
    getFindings(id).then(setFindings).catch((e) => toast(e.message ?? "Не удалось загрузить находки"));
  }, [id, status, toast]);

  const seek = useCallback((sec: number) => {
    const v = video.current;
    if (!v) return;
    v.currentTime = sec;
    v.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  async function decide(fid: string, next: Decision) {
    const prev = findings;
    setBusyId(fid);
    setFindings((xs) => xs?.map((f) => (f.id === fid ? { ...f, status: next } : f)) ?? xs); // сразу обновляем
    try {
      const saved = await patchFinding(fid, next);
      setFindings((xs) => xs?.map((f) => (f.id === fid ? saved : f)) ?? xs);
    } catch (e) {
      setFindings(prev); // откат
      toast(e instanceof Error ? e.message : "Не удалось сохранить решение");
    } finally {
      setBusyId(null);
    }
  }

  async function report() {
    if (!insp) return;
    setReportBusy(true);
    try {
      await downloadReport(insp.id, insp.title);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Отчёт недоступен");
    } finally {
      setReportBusy(false);
    }
  }

  const counters = useMemo(() => {
    const c = { new: 0, confirmed: 0, rejected: 0, reshoot: 0 };
    findings?.forEach((f) => (c[f.status] += 1));
    return c;
  }, [findings]);
  const visible = useMemo(() => (findings ?? []).filter((f) => filter === "all" || f.status === filter), [findings, filter]);

  if (notFound) {
    return (
      <div className="py-20 text-center">
        <p className="text-lg">Инспекция не найдена</p>
        <Link href="/inspections" className="mt-3 inline-block text-accent hover:underline">К списку инспекций</Link>
      </div>
    );
  }
  if (!insp) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-8 w-1/3" />
        <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="skeleton aspect-video" />
          <div className="skeleton h-96" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/inspections" className="text-sm text-muted hover:text-fg">← Инспекции</Link>
        <h1 className="text-2xl font-semibold tracking-tight">{insp.title}</h1>
        <StatusBadge status={insp.status} />
        <span className="text-sm text-muted">
          {fmtDate(insp.created_at)} · длительность {insp.duration_sec ? fmtTimecode(insp.duration_sec) : "—"}
        </span>
        <button
          onClick={report}
          disabled={insp.status !== "done" || reportBusy}
          className="ml-auto rounded-md bg-accent px-4 py-2 text-sm font-medium text-black disabled:opacity-40"
        >
          {reportBusy ? "Готовим отчёт…" : "Скачать отчёт"}
        </button>
      </div>

      {insp.status === "failed" && (
        <div className="rounded-xl border border-danger/40 bg-danger/10 p-5" role="alert">
          <p className="font-medium text-danger">Обработка не удалась{insp.error_code ? ` (${insp.error_code})` : ""}</p>
          <p className="mt-1 text-sm">{errorText(insp.error_code, insp.error_message)}</p>
          <Link href="/inspections" className="mt-3 inline-block rounded-md border border-danger/40 px-3 py-1.5 text-sm text-danger hover:bg-danger/10">
            Загрузить заново
          </Link>
        </div>
      )}

      {(insp.status === "queued" || insp.status === "processing") && (
        <div className="rounded-xl border border-line bg-surface p-5">
          <p className="text-sm">
            {insp.status === "queued" ? "Ожидает обработки…" : `Обработка: ${Math.round((insp.progress ?? 0) * 100)}%`}
          </p>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface2">
            <div
              className={`h-full bg-accent transition-all ${insp.status === "queued" ? "w-1/12 animate-pulse" : ""}`}
              style={insp.status === "processing" ? { width: `${Math.max(3, Math.round((insp.progress ?? 0) * 100))}%` } : undefined}
            />
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div>
          <video
            ref={video}
            src={videoUrl(insp.id)}
            controls
            preload="metadata"
            className="aspect-video w-full rounded-xl border border-line bg-black"
          />
          {insp.status === "done" && (
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[
                ["FPS обработки", insp.fps?.toFixed(1) ?? "—"],
                ["Декодирование", insp.stage_times?.decode != null ? `${insp.stage_times.decode.toFixed(1)} с` : "—"],
                ["Детекция", insp.stage_times?.detect != null ? `${insp.stage_times.detect.toFixed(1)} с` : "—"],
                ["Файл", insp.filename],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-line bg-surface px-3 py-2">
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="truncate font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        <aside className="space-y-3">
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg border border-line bg-surface p-2"><div className="text-lg font-semibold">{counters.new}</div>новых</div>
            <div className="rounded-lg border border-ok/30 bg-surface p-2"><div className="text-lg font-semibold text-ok">{counters.confirmed}</div>подтверждено</div>
            <div className="rounded-lg border border-danger/30 bg-surface p-2"><div className="text-lg font-semibold text-danger">{counters.rejected}</div>отклонено</div>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  filter === f.key ? "border-accent bg-accent/10 text-accent" : "border-line text-muted hover:text-fg"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="max-h-[70vh] space-y-3 overflow-y-auto pr-1">
            {insp.status !== "done" && <p className="py-6 text-center text-sm text-muted">Находки появятся после обработки</p>}
            {insp.status === "done" && findings === null && <div className="skeleton h-40" />}
            {insp.status === "done" && findings?.length === 0 && (
              <p className="py-6 text-center text-sm text-muted">Находок нет</p>
            )}
            {visible.map((f) => (
              <FindingCard key={f.id} inspectionId={insp.id} finding={f} busy={busyId === f.id} onSeek={seek} onDecide={decide} />
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
