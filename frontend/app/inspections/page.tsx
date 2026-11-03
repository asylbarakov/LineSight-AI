"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/Badges";
import { useToast } from "@/components/Toast";
import { UploadForm } from "@/components/UploadForm";
import { listInspections } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { InspectionSummary } from "@/lib/types";

export default function InspectionsPage() {
  const router = useRouter();
  const toast = useToast();
  const [rows, setRows] = useState<InspectionSummary[] | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      listInspections()
        .then((r) => alive && setRows([...r].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))))
        .catch((e) => alive && toast(e.message ?? "Не удалось загрузить список"));
    load();
    const t = setInterval(load, 4000); // статусы в списке обновляются сами
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [toast]);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold tracking-tight">Инспекции</h1>
      <UploadForm onUploaded={(id) => router.push(`/inspections/${id}`)} />
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-5 py-3 font-medium">Название</th>
              <th className="px-5 py-3 font-medium">Дата</th>
              <th className="px-5 py-3 font-medium">Статус</th>
              <th className="px-5 py-3 text-right font-medium">Находок</th>
            </tr>
          </thead>
          <tbody>
            {rows === null &&
              [0, 1, 2].map((i) => (
                <tr key={i} className="border-b border-line/60">
                  <td colSpan={4} className="px-5 py-3"><div className="skeleton h-5 w-full" /></td>
                </tr>
              ))}
            {rows?.map((r) => (
              <tr key={r.id} className="border-b border-line/60 transition-colors last:border-0 hover:bg-surface2">
                <td className="px-5 py-3">
                  <Link href={`/inspections/${r.id}`} className="font-medium text-fg hover:text-accent">{r.title}</Link>
                </td>
                <td className="px-5 py-3 text-muted">{fmtDate(r.created_at)}</td>
                <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                <td className="px-5 py-3 text-right tabular-nums">{r.findings_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows?.length === 0 && <p className="px-5 py-10 text-center text-sm text-muted">Инспекций пока нет</p>}
      </div>
    </div>
  );
}
