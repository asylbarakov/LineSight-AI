import Link from "next/link";
import { MockBadge } from "@/components/Badges";
import { DEMO_SECTIONS } from "@/lib/demoSections";

export default function SectionsPage() {
  return <div className="space-y-5">
    <div><div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold tracking-tight">Участки ЛЭП</h1><MockBadge /></div>
      <p className="mt-2 max-w-3xl text-base leading-6 text-muted">Демонстрационный каталог. Участок — объект инфраструктуры, инспекция — отдельная видеозапись его обследования. Эти примеры не связаны с загруженными видео.</p></div>
    <section className="rounded-xl border border-warn/40 bg-warn-soft p-4 text-sm" aria-label="Демонстрационные данные">
      <p className="font-semibold text-warn">Все участки на этой странице вымышленные</p>
      <p className="mt-1 text-xs leading-5">Даты инспекций, находки и статусы не назначены. Реальные результаты доступны в разделе «Инспекции».</p>
    </section>
    <section className="rounded-[10px] border border-line bg-surface p-4" aria-label="Демо-участки">
      <div className="mb-3 hidden grid-cols-[minmax(0,1fr)_160px_160px] gap-4 rounded-md bg-surface2 px-4 py-3 text-xs font-semibold text-muted md:grid">
        <span>Участок</span><span>Последняя инспекция</span><span>Статус инспекции</span>
      </div>
      <div className="divide-y divide-line">
        {DEMO_SECTIONS.map((section) => <details key={section.id} className="group rounded-lg open:bg-surface2/50">
          <summary className="cursor-pointer rounded-lg px-4 py-4 text-sm marker:text-muted">
            <span className="ml-1 inline-grid w-[calc(100%-24px)] gap-2 align-middle md:grid-cols-[minmax(0,1fr)_160px_160px] md:gap-4">
              <span className="font-semibold">{section.title} <span className="ml-1 text-xs font-normal text-warn">Демо</span></span>
              <span className="text-xs text-muted">Не привязана</span><span className="text-xs text-muted">Нет данных</span>
            </span>
          </summary>
          <div className="space-y-2 px-4 pb-5 text-xs leading-5 text-muted"><p>{section.description}</p>
            <p>После подключения каталога здесь будут сведения об участке и связанные инспекции. Этот макет не создаёт и не изменяет реальные данные.</p>
            <Link href="/inspections" className="inline-block font-medium text-accent hover:underline">Открыть реальные инспекции →</Link>
          </div>
        </details>)}
      </div>
    </section>
    <Link href="/dashboard" className="inline-block text-xs text-accent hover:underline">← Вернуться к обзору</Link>
  </div>;
}
