"use client";

import { forwardRef, useCallback, useImperativeHandle, useRef, useState } from "react";
import { videoUrl } from "@/lib/api";
import { scrollToElement } from "@/lib/motion";
import { findingTimecode, isVideoDuration } from "@/lib/timeline";
import type { Finding } from "@/lib/types";
import { VideoTimeline } from "./VideoTimeline";

export interface VideoPlayerHandle { seekTo: (seconds: number) => void; getCurrentTime: () => number | null }
interface Props {
  inspectionId: string;
  durationSec: number | null;
  findings: Finding[];
  selectedId: string | null;
  findingsLoading?: boolean;
  findingsUnavailable?: boolean;
  emptyMessage?: string;
  onSelectFinding: (finding: Finding) => void;
  onTimeChange?: (seconds: number | null) => void;
}

export const VideoPlayer = forwardRef<VideoPlayerHandle, Props>(function VideoPlayer({ inspectionId, durationSec,
  findings, selectedId, findingsLoading, findingsUnavailable, emptyMessage, onSelectFinding, onTimeChange }, ref) {
  const video = useRef<HTMLVideoElement>(null);
  const pendingSeek = useRef<number | null>(null);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [videoError, setVideoError] = useState(false);
  const [seekError, setSeekError] = useState<string | null>(null);
  const [waitingForSeek, setWaitingForSeek] = useState(false);

  const seekTo = useCallback((seconds: number) => {
    const el = video.current;
    if (!el || !Number.isFinite(seconds) || seconds < 0) {
      setSeekError("Не удалось перейти к находке: некорректный таймкод.");
      return;
    }
    setSeekError(null);
    if (el.readyState < 1) {
      pendingSeek.current = seconds;
      setWaitingForSeek(true);
      return;
    }
    if (isVideoDuration(el.duration) && seconds > el.duration) {
      pendingSeek.current = null;
      setWaitingForSeek(false);
      setSeekError(`Таймкод ${findingTimecode(seconds)} находится за пределами видео.`);
      return;
    }
    try {
      el.currentTime = seconds;
      setCurrentTime(seconds);
      pendingSeek.current = null;
      setWaitingForSeek(false);
    } catch {
      setSeekError("Не удалось перемотать видео. Дождитесь загрузки и повторите переход.");
    }
  }, []);

  useImperativeHandle(ref, () => ({ seekTo: (seconds) => {
    seekTo(seconds);
    scrollToElement(video.current);
  }, getCurrentTime: () => video.current && video.current.readyState >= 1 && !video.current.error ? video.current.currentTime : null }), [seekTo]);

  function syncDuration() {
    const el = video.current;
    if (el && isVideoDuration(el.duration)) setDuration(el.duration);
  }

  function retryVideo() {
    const el = video.current;
    if (!el) return;
    if (pendingSeek.current === null && Number.isFinite(el.currentTime)) pendingSeek.current = el.currentTime;
    setVideoError(false);
    setLoaded(false);
    setSeekError(null);
    el.load();
  }

  return (
    <section className="min-w-0 overflow-visible rounded-md border border-line bg-surface" aria-label="Видео инспекции">
      <div className="relative rounded-t-lg bg-media">
        <video ref={video} src={videoUrl(inspectionId)} controls preload="metadata"
          onLoadedMetadata={() => { syncDuration(); setLoaded(true); setVideoError(false); if (pendingSeek.current !== null) seekTo(pendingSeek.current); onTimeChange?.(video.current?.currentTime ?? 0); }}
          onDurationChange={syncDuration} onTimeUpdate={(e) => {setCurrentTime(e.currentTarget.currentTime); onTimeChange?.(e.currentTarget.currentTime);}}
          onSeeked={(e) => {setCurrentTime(e.currentTarget.currentTime); onTimeChange?.(e.currentTarget.currentTime);}} onError={() => { setVideoError(true); setLoaded(false); onTimeChange?.(null); }}
          className="inspection-video aspect-video w-full rounded-t-md bg-media" aria-label="Запись инспекции" />
        {!loaded && !videoError && <p className="pointer-events-none absolute left-4 top-4 rounded-md bg-surface px-3 py-2 text-xs text-muted" role="status">Загрузка видео…</p>}
      </div>
      {videoError && <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line p-4" role="alert">
        <p className="max-w-lg text-sm text-danger">Видео недоступно. Проверьте соединение. Если браузер не поддерживает кодек MP4, потребуется совместимая запись.</p>
        <button type="button" onClick={retryVideo} className="btn">Повторить загрузку видео</button>
      </div>}
      {(seekError || (waitingForSeek && !videoError)) && <p className="px-4 py-3 text-xs text-warn" role={seekError ? "alert" : "status"}>
        {seekError ?? "Переход к находке будет выполнен после загрузки видео."}</p>}
      <VideoTimeline findings={findings} duration={isVideoDuration(duration) ? duration : durationSec ?? 0}
        currentTime={currentTime} selectedId={selectedId} loading={findingsLoading} unavailable={findingsUnavailable}
        emptyMessage={emptyMessage} onSelect={onSelectFinding} onSeek={seekTo} />
    </section>
  );
});
