"use client";

import { useRef, useState } from "react";
import { ApiError, uploadInspection } from "@/lib/api";
import { useToast } from "./Toast";

export const MAX_UPLOAD_MB = 500;

/** Клиентская проверка до отправки: тип и размер. Возвращает текст ошибки или null. */
export function validateFile(file: Pick<File, "name" | "size">, maxMb = MAX_UPLOAD_MB): string | null {
  if (!file.name.toLowerCase().endsWith(".mp4")) return "Принимаются только файлы MP4";
  if (file.size > maxMb * 1024 * 1024) return `Файл больше ${maxMb} МБ`;
  if (file.size === 0) return "Файл пустой";
  return null;
}

export function UploadForm({ onUploaded }: { onUploaded: (id: string) => void }) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function pick(f: File | null) {
    setError(null);
    if (!f) return setFile(null);
    const err = validateFile(f);
    if (err) {
      setFile(null);
      setError(err);
      return;
    }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.mp4$/i, ""));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      const r = await uploadInspection(file, title.trim(), setProgress);
      toast("Видео загружено, обработка началась", "success");
      onUploaded(r.id);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Не удалось загрузить файл";
      setError(msg);
      toast(msg);
      setProgress(null);
    }
  }

  const uploading = progress !== null;
  return (
    <form onSubmit={submit} className="rounded-xl border border-line bg-surface p-5">
      <h2 className="section-title">Новая инспекция</h2>
      <p className="mt-1 max-w-prose text-base text-muted">MP4 до {MAX_UPLOAD_MB} МБ. Одна загрузка создаёт одну видеоинспекцию.</p>
      <div className="mt-4 grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
        <label className="block text-label">
          <span className="mb-1 block text-muted">Видео (MP4)</span>
          <input
            ref={input}
            type="file"
            accept="video/mp4,.mp4"
            disabled={uploading}
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-muted file:mr-3 file:rounded-md file:border-0 file:bg-surface2 file:px-3 file:py-2 file:text-sm file:text-fg"
          />
        </label>
        <label className="block text-label">
          <span className="mb-1 block text-muted">Название</span>
          <input
            value={title}
            disabled={uploading}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Облёт участка 1"
            className="min-h-11 w-full rounded-md border border-control bg-field px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </label>
        <button
          type="submit"
          disabled={!file || uploading}
          className="btn-primary px-5"
        >
          {uploading ? "Загрузка…" : "Загрузить"}
        </button>
      </div>
      {uploading && (
        <div className="mt-4" aria-label="Прогресс загрузки">
          <div role="progressbar" aria-label="Загрузка MP4" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((progress ?? 0) * 100)} className="h-2 overflow-hidden rounded-full bg-surface2">
            <div className="h-full bg-accent transition-all" style={{ width: `${Math.round((progress ?? 0) * 100)}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted">{Math.round((progress ?? 0) * 100)}%</p>
        </div>
      )}
      {error && <p className="mt-3 text-sm text-danger" role="alert">{error}</p>}
    </form>
  );
}
