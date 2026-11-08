"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { InspectionTable } from "@/components/InspectionTable";
import { InspectionFilters } from "@/components/InspectionFilters";
import { useResource } from "@/components/useResource";
import { ResourceError } from "@/components/ResourceError";
import { filterInspections, type InspectionFilter } from "@/lib/dashboard";
import { MAX_UPLOAD_MB, UploadForm } from "@/components/UploadForm";
import { listInspections } from "@/lib/api";
import type { InspectionSummary } from "@/lib/types";

export default function InspectionsPage() {
  const router = useRouter();
  const { data: rows, loading, error, retry } = useResource<InspectionSummary[]>(listInspections, 4000);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<InspectionFilter>("all");
  const uploadSection = useRef<HTMLDetailsElement>(null);
  const filtered = useMemo(() => filterInspections(rows ?? [], query, status), [rows, query, status]);
  useEffect(() => {
    const revealUpload = () => {
      if (window.location.hash === "#new-inspection" && uploadSection.current) uploadSection.current.open = true;
    };
    revealUpload();
    window.addEventListener("hashchange", revealUpload);
    return () => window.removeEventListener("hashchange", revealUpload);
  }, []);

  return (
    <div className="space-y-5">
      <div><h1 className="page-title">Инспекции</h1><p className="mt-2 text-sm text-muted">Загрузите видео, проверьте находки и сформируйте отчёт.</p></div>
      <details ref={uploadSection} id="new-inspection" className="group scroll-mt-24 rounded-lg border border-line bg-surface">
        <summary className="flex min-h-11 cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-4 py-3 hover:bg-surface2 [&::-webkit-details-marker]:hidden">
          <span aria-hidden="true" className="text-xl leading-none group-open:rotate-90">›</span>
          <span className="section-title">Новая инспекция</span><span className="text-xs text-muted">MP4 · до {MAX_UPLOAD_MB} МБ</span>
        </summary>
        {/* Keep mounted: closing this disclosure must not clear the file, title or active upload. */}
        <UploadForm onUploaded={(id) => router.push(`/inspections/${id}`)} />
      </details>
      {error && <ResourceError error={error} loading={loading} onRetry={retry} />}
      <section className="min-w-0" aria-label="Список инспекций">
        <InspectionFilters query={query} status={status} onQueryChange={setQuery} onStatusChange={setStatus} />
        <div className="mt-3 rounded-lg border border-line bg-surface">
          <InspectionTable rows={filtered} loading={rows === null && !error} emptyMessage={error && rows === null ? "Список недоступен. Повторите загрузку." : query || status !== "all" ? "Инспекции по вашему запросу не найдены" : undefined} />
        </div>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted" aria-live="polite">
          <p>{rows === null ? "Список не загружен" : `Показано ${filtered.length} из ${rows.length}`}</p>
          {(query || status !== "all") && <button type="button" className="quiet-link text-accent" onClick={() => { setQuery(""); setStatus("all"); }}>Сбросить поиск и фильтр</button>}
        </div>
      </section>
    </div>
  );
}
