"use client";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { findingMarkerStyle, findingTimecode, groupTimelineFindings, isVideoDuration } from "@/lib/timeline";
import { FINDING_STATUS_RU, PRIORITY_RU, typeRu } from "@/lib/texts";
import type { Finding } from "@/lib/types";
import { Icon, type IconName } from "./Icon";

interface Props {
  findings: Finding[]; duration: number; currentTime: number; selectedId: string | null;
  loading?: boolean; unavailable?: boolean; emptyMessage?: string;
  onSelect: (finding: Finding) => void; onSeek: (seconds: number) => void;
}
const iconFor = (f: Pick<Finding, "type" | "priority">): IconName => findingMarkerStyle(f).insufficient ? "visibility" : f.priority === "high" ? "high" : f.priority === "medium" ? "medium" : "low";
const labelFor = (f: Finding) => `${findingTimecode(f.timecode_sec)} · ${typeRu(f.type)} · Приоритет: ${PRIORITY_RU[f.priority]}`;

export function VideoTimeline({ findings, duration, currentTime, selectedId, loading, unavailable, emptyMessage = "Находок нет. Видео доступно для ручной проверки.", onSelect, onSeek }: Props) {
  const track = useRef<HTMLDivElement>(null);
  const groupButtons = useRef(new Map<string, HTMLButtonElement>());
  const [width, setWidth] = useState(0);
  const [hovered, setHovered] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const tooltipId = useId();
  const groupId = useId();
  const valid = isVideoDuration(duration);
  const time = valid ? Math.min(duration, Math.max(0, Number.isFinite(currentTime) ? currentTime : 0)) : 0;
  const groups = useMemo(() => groupTimelineFindings(findings, duration, width), [findings, duration, width]);
  const tooltip = groups.find(group => group.findings[0].id === hovered);
  const open = groups.find(group => group.findings[0].id === expanded);
  const invalid = valid ? findings.filter(f => !Number.isFinite(f.timecode_sec) || f.timecode_sec < 0 || f.timecode_sec > duration).length : 0;
  useEffect(() => {
    const element = track.current;
    if (!element) return;
    const measure = () => setWidth(element.getBoundingClientRect().width);
    measure();
    const observer = new ResizeObserver(measure); observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const tooltipX = tooltip ? Math.max(Math.min(width / 2, 140), Math.min(width - Math.min(width / 2, 140), tooltip.percent / 100 * width)) : 0;
  function closeGroup() {
    if (expanded) groupButtons.current.get(expanded)?.focus();
    setExpanded(null);
    setHovered(null);
  }
  return <div className="border-t border-line p-3" aria-label="Шкала видео с находками"
    onMouseLeave={() => setHovered(null)} onKeyDown={event => { if (event.key === "Escape") closeGroup(); }}>
    <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
      <h2 className="section-title">Находки на видео</h2><span className="text-xs tabular-nums text-muted">{findingTimecode(time)} / {valid ? findingTimecode(duration) : "—"}</span>
    </div>
    <div className="relative mx-[22px]" ref={track}>
      {tooltip && <div role="tooltip" id={tooltipId} onMouseEnter={() => setHovered(tooltip.findings[0].id)}
        className="absolute bottom-full z-20 mb-2 w-64 max-w-[calc(100vw-64px)] -translate-x-1/2 rounded-md border border-control bg-surface2 p-3 text-xs shadow-lg" style={{left: tooltipX}}>
        {tooltip.findings.length > 1 && <p className="mb-1 font-medium">Группа {findingTimecode(tooltip.findings[0].timecode_sec)}–{findingTimecode(tooltip.findings[tooltip.findings.length - 1].timecode_sec)}</p>}
        <p className="font-medium">{labelFor(tooltip.findings.find(f => f.id === selectedId) ?? tooltip.findings[0])}</p>
        {tooltip.findings.length > 1 && <p className="mt-2 text-muted">Находок в группе: {tooltip.findings.length}. Выберите точный момент после нажатия.</p>}
        <p className="mt-1 text-muted">Статус: {FINDING_STATUS_RU[(tooltip.findings.find(f => f.id === selectedId) ?? tooltip.findings[0]).status]}</p>
      </div>}
      <input type="range" min={0} max={valid ? duration : 1} step="any" value={time} disabled={!valid}
        onChange={event => onSeek(Number(event.target.value))} aria-label="Позиция воспроизведения"
        aria-valuetext={`${findingTimecode(time)} из ${valid ? findingTimecode(duration) : "неизвестной длительности"}`}
        className="block h-6 w-full accent-accent" />
      <div className="relative h-11">
        {valid && <span aria-hidden="true" className="absolute inset-y-0 w-px bg-accent/60" style={{left: `${time / duration * 100}%`}} />}
        {groups.map(group => {
          const first = group.findings[0];
          const selected = group.findings.find(f => f.id === selectedId);
          const representative = selected ?? first;
          const multiple = group.findings.length > 1;
          return <button type="button" key={first.id} ref={node => { if (node) groupButtons.current.set(first.id, node); else groupButtons.current.delete(first.id); }} data-finding-marker={representative.id} data-marker-members={group.findings.map(f => f.id).join(" ")}
            aria-label={`${labelFor(representative)}${multiple ? ` · Находок в группе: ${group.findings.length}, ${findingTimecode(first.timecode_sec)}–${findingTimecode(group.findings[group.findings.length - 1].timecode_sec)}` : ""}`} aria-pressed={!!selected}
            aria-expanded={multiple ? expanded === first.id : undefined} aria-controls={multiple && expanded === first.id ? groupId : undefined}
            aria-describedby={hovered === first.id ? tooltipId : undefined}
            onMouseEnter={() => setHovered(first.id)} onFocus={() => setHovered(first.id)} onBlur={() => setHovered(null)}
            onClick={() => { onSelect(representative); setExpanded(multiple ? first.id : null); }}
            className={`timeline-marker absolute top-0 flex -translate-x-1/2 items-center justify-center rounded-md hover:bg-surface2 ${selected ? "bg-accent-soft ring-1 ring-accent" : ""}`}
            style={{left: `${group.percent}%`}}>
            <Icon name={iconFor(representative)} size={20} style={{color: findingMarkerStyle(representative).color}} />
            {multiple && <span className="absolute -right-1 top-0 rounded border border-line bg-surface px-1 text-xs tabular-nums text-fg">{group.findings.length}</span>}
          </button>;
        })}
      </div>
    </div>
    {open && <section id={groupId} aria-label="Находки с близкими таймкодами" className="mt-4 rounded-md border border-line bg-surface2 p-2">
      <div className="flex items-center justify-between pl-2"><h3 className="text-xs font-medium">Близкие таймкоды · {open.findings.length}</h3><button type="button" className="icon-button" aria-label="Закрыть группу находок" onClick={closeGroup}><Icon name="close" size={16} /></button></div>
      <div className="max-h-48 overflow-y-auto">{open.findings.map(f => <button key={f.id} type="button" onClick={() => onSelect(f)} aria-pressed={f.id === selectedId} aria-label={labelFor(f)}
        className={`flex min-h-11 w-full items-center gap-3 rounded px-2 py-2 text-left text-sm hover:bg-surface ${f.id === selectedId ? "bg-surface ring-1 ring-inset ring-accent" : ""}`}>
        <Icon name={iconFor(f)} className="shrink-0" style={{color: findingMarkerStyle(f).color}} /><span className="shrink-0 tabular-nums">{findingTimecode(f.timecode_sec)}</span><span className="min-w-0 flex-1 break-words">{typeRu(f.type)}</span><span className="ml-auto hidden text-xs text-muted sm:inline">{PRIORITY_RU[f.priority]}</span>
      </button>)}</div>
    </section>}
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted" aria-label="Приоритеты находок">
      {(["high", "medium", "low", "insufficient_data"] as const).map(priority => {
        const sample = {type: "", priority};
        return <span key={priority} className="inline-flex items-center gap-1.5"><Icon name={iconFor(sample)} size={16} style={{color: findingMarkerStyle(sample).color}} />{PRIORITY_RU[priority]}</span>;
      })}
    </div>
    <div className="text-xs leading-5 text-muted empty:hidden [&:not(:empty)]:mt-2" aria-live="polite">
      {loading ? <p>Загрузка находок…</p> : unavailable ? <p>Маркеры недоступны. Повторите загрузку в панели находок.</p> : !findings.length ? <p>{emptyMessage}</p> : !valid ? <p>Ожидание длительности видео для расстановки маркеров.</p> : null}
      {invalid > 0 && <p className="text-warn">Находок с таймкодами вне видео: {invalid}. Они доступны в списке.</p>}
    </div>
  </div>;
}
