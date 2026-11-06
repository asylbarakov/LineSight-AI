"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { StatusBadge } from "@/components/Badges";
import { FindingCard } from "@/components/FindingCard";
import { VideoPlayer, type VideoPlayerHandle } from "@/components/VideoPlayer";
import { ApiError, downloadReport, getFindings, getInspection, patchFinding } from "@/lib/api";
import { fmtDate, fmtTimecode } from "@/lib/format";
import { errorText } from "@/lib/texts";
import { replaceFinding, rollbackFinding } from "@/lib/review";
import { scrollToElement } from "@/lib/motion";
import { Icon } from "@/components/Icon";
import type { Decision, Finding, FindingStatus, InspectionDetail } from "@/lib/types";

type Filter = "all" | FindingStatus;
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "Все" }, { key: "new", label: "Новые" },
  { key: "confirmed", label: "Подтверждённые" }, { key: "rejected", label: "Отклонённые" },
  { key: "reshoot", label: "Переснять" },
];
const retryClass = "btn";
const messageFor = (error: unknown, fallback: string) => error instanceof ApiError ? error.message : fallback;

function LoadError({ title, message, onRetry, busy = false }: { title: string; message: string; onRetry: () => void; busy?: boolean }) {
  return <div className="rounded-xl border border-line bg-surface p-4" role="alert">
    <p className="text-sm font-medium text-danger">{title}</p>
    <p className="mt-1 text-sm text-muted">{message}</p>
    <button type="button" onClick={onRetry} disabled={busy} className={`mt-3 ${retryClass}`}>{busy ? "Загрузка…" : "Повторить"}</button>
  </div>;
}

export default function InspectionPage() {
  const { id } = useParams<{ id: string }>();
  // Remount so requests and selection cannot leak into another inspection.
  return <InspectionDetails key={id} id={id} />;
}

function InspectionDetails({ id }: { id: string }) {
  const player = useRef<VideoPlayerHandle>(null);
  const cardRefs = useRef(new Map<string, HTMLDivElement>());
  const pendingDecisions = useRef(new Set<string>());
  const mounted = useRef(true);
  const [insp, setInsp] = useState<InspectionDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [inspectionError, setInspectionError] = useState<string | null>(null);
  const [inspectionLoading, setInspectionLoading] = useState(true);
  const [inspectionRetry, setInspectionRetry] = useState(0);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [findingsLoading, setFindingsLoading] = useState(false);
  const [findingsError, setFindingsError] = useState<string | null>(null);
  const [findingsRetry, setFindingsRetry] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [revealCard, setRevealCard] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [busyIds, setBusyIds] = useState(new Set<string>());
  const [decisionErrors, setDecisionErrors] = useState<Record<string, { message: string; next: Decision }>>({});
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const status = insp?.status;
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setInspectionLoading(true);
    setInspectionError(null);
    setNotFound(false);
    const tick = async () => {
      try {
        const detail = await getInspection(id);
        if (!alive) return;
        setInsp(detail);
        setInspectionError(null);
        setInspectionLoading(false);
        if (detail.status === "queued" || detail.status === "processing") timer = setTimeout(tick, 2000);
      } catch (error) {
        if (!alive) return;
        setInspectionLoading(false);
        if (error instanceof ApiError && error.status === 404) setNotFound(true);
        else {
          setInspectionError(messageFor(error, "Не удалось получить данные инспекции. Проверьте соединение."));
          if (!(error instanceof ApiError && error.status === 401)) timer = setTimeout(tick, 4000);
        }
      }
    };
    void tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [id, inspectionRetry]);

  useEffect(() => {
    if (status !== "done") return;
    let alive = true;
    setFindingsLoading(true);
    setFindingsError(null);
    getFindings(id).then((result) => {
      if (alive) setFindings(result);
    }).catch((error) => {
      if (alive) setFindingsError(messageFor(error, "Не удалось загрузить находки. Проверьте соединение."));
    }).finally(() => { if (alive) setFindingsLoading(false); });
    return () => { alive = false; };
  }, [id, status, findingsRetry]);

  useEffect(() => {
    if (!revealCard || !selectedId) return;
    scrollToElement(cardRefs.current.get(selectedId));
    setRevealCard(false);
  }, [revealCard, selectedId, filter, panelOpen]);

  function selectFinding(finding: Finding, fromTimeline = false) {
    setSelectedId(finding.id);
    player.current?.seekTo(finding.timecode_sec);
    if (fromTimeline) {
      setPanelOpen(true);
      if (filter !== "all" && filter !== finding.status) setFilter("all");
      // Keep the timeline/group chooser in view on stacked mobile layouts.
      const workspace = cardRefs.current.get(finding.id)?.closest(".inspection-workspace");
      setRevealCard((workspace?.getBoundingClientRect().width ?? 0) >= 900);
    }
  }

  async function decide(fid: string, next: Decision) {
    const previous = findings?.find((f) => f.id === fid);
    if (!previous || pendingDecisions.current.has(fid)) return;
    pendingDecisions.current.add(fid);
    setBusyIds(new Set(pendingDecisions.current));
    setDecisionErrors((errors) => { const copy = { ...errors }; delete copy[fid]; return copy; });
    setFindings((xs) => xs?.map((f) => f.id === fid ? { ...f, status: next } : f) ?? xs);
    try {
      const saved = await patchFinding(fid, next);
      if (mounted.current) setFindings((xs) => xs ? replaceFinding(xs, saved) : xs);
    } catch (error) {
      if (mounted.current) {
        // Only roll back this finding, preserving other in-flight decisions.
        setFindings((xs) => xs ? rollbackFinding(xs, previous, next) : xs);
        setDecisionErrors((errors) => ({ ...errors, [fid]: { message: messageFor(error, "Не удалось сохранить решение."), next } }));
        setFilter((current) => current !== "all" && current !== previous.status ? "all" : current);
      }
    } finally {
      pendingDecisions.current.delete(fid);
      if (mounted.current) setBusyIds(new Set(pendingDecisions.current));
    }
  }

  async function report() {
    if (!insp || reportBusy) return;
    setReportBusy(true);
    setReportError(null);
    try { await downloadReport(insp.id, insp.title); }
    catch (error) { if (mounted.current) setReportError(messageFor(error, "Не удалось скачать отчёт. Проверьте соединение и повторите попытку.")); }
    finally { if (mounted.current) setReportBusy(false); }
  }

  const counters = useMemo(() => {
    const result = { new: 0, confirmed: 0, rejected: 0, reshoot: 0 };
    findings?.forEach((f) => { result[f.status] += 1; });
    return result;
  }, [findings]);
  const visible = useMemo(() => (findings ?? []).filter((f) => filter === "all" || f.status === filter), [findings, filter]);
  const progress = Math.min(100, Math.max(0, Math.round((insp?.progress ?? 0) * 100)));
  const total = findings?.length;

  if (notFound) return <div className="rounded-2xl border border-line bg-surface px-6 py-16 text-center">
    <h1 className="page-title">Инспекция не найдена</h1>
    <p className="mt-2 text-sm text-muted">Проверьте ссылку или выберите другую инспекцию.</p>
    <Link href="/inspections" className="mt-4 inline-block text-sm text-accent hover:underline">К списку инспекций</Link>
  </div>;

  if (!insp) return <div className="space-y-5">
    <Link href="/inspections" className="text-sm text-muted hover:text-fg">← Инспекции</Link>
    {inspectionError ? <LoadError title="Не удалось открыть инспекцию" message={inspectionError}
      onRetry={() => setInspectionRetry((x) => x + 1)} busy={inspectionLoading} />
      : <div className="space-y-4" role="status" aria-label="Загрузка инспекции"><div className="skeleton h-8 w-1/3" />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]"><div className="skeleton aspect-video" /><div className="skeleton h-96" /></div>
      </div>}
  </div>;

  return <div className="space-y-5">
    <header className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2"><div className="flex flex-wrap items-center gap-3">
          <h1 className="page-title break-words">{insp.title}</h1><StatusBadge status={insp.status} />
        </div><p className="text-xs text-muted">{fmtDate(insp.created_at)} · Длительность {insp.duration_sec ? fmtTimecode(insp.duration_sec) : "—"}</p></div>
        <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={report} disabled={insp.status !== "done" || reportBusy || busyIds.size > 0}
          className="btn">
          {reportBusy ? "Готовим отчёт…" : "Скачать PDF-отчёт"}</button>
        <button type="button" className="btn" aria-label={panelOpen ? "Скрыть находки" : `Показать находки${total !== undefined ? ` · ${total}` : ""}`}
          title={panelOpen ? "Скрыть находки" : "Показать находки"} aria-expanded={panelOpen} aria-controls="findings-panel" onClick={() => setPanelOpen(open => !open)}>
          <Icon name="panel" /><span className="hidden sm:inline">{panelOpen ? "Скрыть находки" : `Находки${total !== undefined ? ` · ${total}` : ""}`}</span></button>
        </div>
      </div>
      {reportError && <LoadError title="Отчёт недоступен" message={reportError} onRetry={report} busy={reportBusy || busyIds.size > 0} />}
    </header>

    {inspectionError && <LoadError title="Не удалось обновить инспекцию" message={`${inspectionError} Показаны последние полученные данные; обновление будет повторено автоматически.`}
      onRetry={() => setInspectionRetry((x) => x + 1)} busy={inspectionLoading} />}

    {insp.status === "failed" && <div className="rounded-xl border border-line bg-surface p-5" role="alert">
      <p className="font-medium text-danger">Обработка не удалась{insp.error_code ? ` (${insp.error_code})` : ""}</p>
      <p className="mt-1 text-sm text-muted">{errorText(insp.error_code, insp.error_message)}</p>
      {insp.error_message && insp.error_message !== errorText(insp.error_code) && (
        <p className="mt-1 break-words text-xs text-muted">Подробности: {insp.error_message}</p>
      )}
      <Link href="/inspections" className={`mt-3 inline-block ${retryClass}`}>Загрузить заново</Link>
    </div>}

    {(insp.status === "queued" || insp.status === "processing") && <div className="rounded-xl border border-line bg-surface p-5">
      <div className="flex items-center justify-between text-sm"><p>{insp.status === "queued" ? "В очереди на обработку" : "Анализ видео"}</p>
        <span className="tabular-nums text-muted">{insp.status === "processing" ? `${progress}%` : "Ожидание"}</span></div>
      <div role="progressbar" aria-label="Обработка инспекции" aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={insp.status === "processing" ? progress : undefined} className="mt-3 h-2 overflow-hidden rounded-full bg-surface2">
        <div className={`h-full bg-accent transition-all ${insp.status === "queued" ? "w-1/12 animate-pulse" : ""}`}
          style={insp.status === "processing" ? { width: `${progress}%` } : undefined} /></div>
      <p className="mt-2 text-xs text-muted">Статус обновляется автоматически. Находки появятся после завершения обработки.</p>
    </div>}

    <section className="inspection-workspace" aria-label="Рабочее место проверки">
    <div className="workbench" data-panel-open={panelOpen}>
      <div className="video-column min-w-0 space-y-3">
        <VideoPlayer ref={player} inspectionId={insp.id} durationSec={insp.duration_sec} findings={findings ?? []}
          selectedId={selectedId} findingsLoading={status === "done" && (findingsLoading || (findings === null && !findingsError))}
          findingsUnavailable={!!findingsError} onSelectFinding={(f) => selectFinding(f, true)}
          emptyMessage={insp.status === "failed" ? "Обработка завершилась ошибкой. Находки недоступны." : insp.status !== "done" ? "Находки появятся после обработки видео." : undefined} />
        {insp.status === "done" && <details className="border-b border-line pb-2">
          <summary className="min-h-11 cursor-pointer rounded text-label leading-[44px] text-muted">Метаданные видео</summary>
          <dl className="grid grid-cols-2 gap-x-5 gap-y-3 pb-3 text-sm sm:grid-cols-4">
          {[["FPS обработки", insp.fps?.toFixed(1) ?? "—"],
            ["Декодирование", insp.stage_times?.decode != null ? `${insp.stage_times.decode.toFixed(1)} с` : "—"],
            ["Детекция", insp.stage_times?.detect != null ? `${insp.stage_times.detect.toFixed(1)} с` : "—"], ["Файл", insp.filename]].map(([label, value]) =>
            <div key={label} className="min-w-0"><dt className="text-xs text-muted">{label}</dt>
              <dd className="mt-1 truncate font-medium" title={value}>{value}</dd></div>)}
        </dl></details>}
      </div>

      <aside id="findings-panel" hidden={!panelOpen} className="min-w-0 space-y-4" aria-label="Результаты анализа">
        <div className="flex items-center justify-between gap-2"><h2 className="section-title">Находки <span className="ml-1 text-sm font-normal text-muted">{total ?? "—"}</span></h2>
          {selectedId && <span className="text-xs text-accent">Выбрана находка</span>}</div>
        <label className="block"><span className="sr-only">Статус находок</span>
          <select value={filter} onChange={event => setFilter(event.target.value as Filter)} className="h-11 w-full rounded-md border border-control px-3 text-sm">
            {FILTERS.map(item => <option key={item.key} value={item.key}>{item.label} · {findings === null ? "—" : item.key === "all" ? total : counters[item.key]}</option>)}
          </select>
        </label>
        {findingsError && <LoadError title="Не удалось загрузить находки" message={findingsError}
          onRetry={() => setFindingsRetry((x) => x + 1)} busy={findingsLoading} />}
        <div className="divide-y divide-line" aria-busy={findingsLoading}>
          {insp.status !== "done" && <p className="rounded-xl border border-dashed border-line px-5 py-8 text-center text-sm text-muted">
            {insp.status === "failed" ? "Находки недоступны из-за ошибки обработки." : "Находки появятся после обработки."}</p>}
          {insp.status === "done" && findings === null && !findingsError && <div className="skeleton h-48" role="status" aria-label="Загрузка находок" />}
          {insp.status === "done" && findings !== null && visible.length === 0 && <div className="rounded-xl border border-dashed border-line px-5 py-8 text-center text-sm text-muted">
            <p>{findings.length === 0 ? "Находок нет" : "В этом фильтре находок нет"}</p>
            {findings.length > 0 && <button type="button" onClick={() => setFilter("all")} className="mt-3 text-accent hover:underline">Показать все находки</button>}
          </div>}
          {visible.map((finding) => <div key={finding.id} ref={(node) => { if (node) cardRefs.current.set(finding.id, node); else cardRefs.current.delete(finding.id); }}>
            <FindingCard inspectionId={insp.id} finding={finding} busy={busyIds.has(finding.id)} selected={selectedId === finding.id}
              onSelect={(f) => selectFinding(f)} onSeek={(seconds) => player.current?.seekTo(seconds)} onDecide={decide}
              error={decisionErrors[finding.id]?.message} onRetry={decisionErrors[finding.id] ? () => decide(finding.id, decisionErrors[finding.id].next) : undefined} />
          </div>)}
        </div>
      </aside>
    </div>
    </section>
  </div>;
}
