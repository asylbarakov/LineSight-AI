import Link from "next/link";
import { fmtDate } from "@/lib/format";
import type { InspectionSummary } from "@/lib/types";
import { StatusBadge } from "./Badges";

export function InspectionTable({ rows, loading = false, emptyMessage = "Инспекций пока нет" }: {
  rows: InspectionSummary[]; loading?: boolean; emptyMessage?: string;
}) {
  return <div className="relative overflow-x-auto">
    <table role="table" className="inspection-table w-full min-w-[650px] text-left text-base">
      <caption className="sr-only">Инспекции: название, дата загрузки, статус обработки и количество находок</caption>
      <thead className="sr-only border-b border-line text-label text-muted sm:not-sr-only"><tr>
        <th scope="col" className="px-3 py-3 font-semibold">Инспекция</th>
        <th scope="col" className="px-3 py-3 font-semibold">Загружено</th>
        <th scope="col" className="px-3 py-3 font-semibold">Статус инспекции</th>
        <th scope="col" className="px-3 py-3 text-right font-semibold">Находки</th>
      </tr></thead>
      <tbody role="rowgroup">
        {loading && [0, 1, 2].map((index) => <tr key={index}><td colSpan={4} className="px-3 py-4"><div className="skeleton h-5" /></td></tr>)}
        {!loading && rows.map((row) => <tr role="row" key={row.id} className="border-b border-line/50 last:border-0 hover:bg-surface2/50">
          <td role="cell" className="inspection-title max-w-[300px] px-3 py-0.5"><Link href={`/inspections/${row.id}`} className="flex min-h-11 items-center gap-3 font-medium hover:text-accent" aria-label={`Открыть инспекцию ${row.title}`}><span className="min-w-0 flex-1 break-words">{row.title}</span><span className="shrink-0 text-muted" aria-hidden="true">↗</span></Link></td>
          <td role="cell" className="inspection-date whitespace-nowrap px-3 py-2 text-muted">{fmtDate(row.created_at)}</td>
          <td role="cell" className="inspection-status px-3 py-2"><StatusBadge status={row.status} /></td>
          <td role="cell" className="inspection-count px-3 py-2 text-right tabular-nums"><span className="sm:hidden">Находки: </span>{row.findings_count}</td>
        </tr>)}
      </tbody>
    </table>
    {!loading && rows.length === 0 && <p className="px-4 py-10 text-center text-sm text-muted">{emptyMessage}</p>}
  </div>;
}
