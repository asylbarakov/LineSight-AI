"use client";

import { useRouter } from "next/navigation";
import { InspectionTable } from "@/components/InspectionTable";
import { useResource } from "@/components/useResource";
import { ResourceError } from "@/components/ResourceError";
import { filterInspections } from "@/lib/dashboard";
import { UploadForm } from "@/components/UploadForm";
import { listInspections } from "@/lib/api";
import type { InspectionSummary } from "@/lib/types";

export default function InspectionsPage() {
  const router = useRouter();
  const { data: rows, loading, error, retry } = useResource<InspectionSummary[]>(listInspections, 4000);

  return (
    <div className="space-y-8">
      <div><h1 className="page-title">Инспекции</h1><p className="mt-2 text-sm text-muted">Загрузите видео, проверьте находки и сформируйте отчёт.</p></div>
      <section id="new-inspection" className="scroll-mt-24"><UploadForm onUploaded={(id) => router.push(`/inspections/${id}`)} /></section>
      {error && <ResourceError error={error} loading={loading} onRetry={retry} />}
      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <InspectionTable rows={filterInspections(rows ?? [], "", "all")} loading={rows === null && !error} emptyMessage={error && rows === null ? "Список недоступен. Повторите загрузку." : undefined} />
      </div>
    </div>
  );
}
