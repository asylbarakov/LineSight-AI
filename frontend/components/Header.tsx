import { NAV_ITEMS } from "./Sidebar";
import { ThemeToggle } from "./ThemeToggle";
import Link from "next/link";

export function Header({ pathname, menuOpen, onToggleMenu, onLogout }: {
  pathname: string; menuOpen: boolean; onToggleMenu: () => void; onLogout: () => void;
}) {
  const page = pathname.startsWith("/inspections/") ? "Проверка видео" : NAV_ITEMS.find((item) => item.href === pathname)?.label ?? "LineSight AI";
  return <header className="sticky top-0 z-30 flex min-h-[var(--header-height)] items-center justify-between gap-3 border-b border-line bg-bg px-4 py-1 md:px-6">
    <div className="flex min-w-0 items-center gap-3">
      <button type="button" onClick={onToggleMenu} aria-expanded={menuOpen} aria-controls="mobile-navigation"
        aria-label={menuOpen ? "Закрыть навигацию" : "Открыть навигацию"}
        className="icon-button lg:hidden">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
          {menuOpen ? <path d="m6 6 12 12M6 18 18 6" /> : <path d="M4 6h16M4 12h16M4 18h16" />}
        </svg>
      </button>
      <div className="flex min-w-0 items-center gap-2 text-sm" aria-label="Текущая страница">
        {pathname.startsWith("/inspections/") ? <><Link href="/inspections" aria-label="Все инспекции" className="inline-flex min-h-11 min-w-11 items-center justify-center text-muted hover:text-fg"><span className="sm:hidden" aria-hidden="true">←</span><span className="hidden sm:inline">Инспекции</span></Link><span className="hidden text-muted sm:inline" aria-hidden="true">/</span></> : null}
        <span className="truncate font-medium">{pathname.startsWith("/inspections/") ? <><span className="sm:hidden">Инспекция</span><span className="hidden sm:inline">{page}</span></> : page}</span>
      </div>
    </div>
    <div className="flex shrink-0 items-center gap-2 sm:gap-4">
      <ThemeToggle />
      <button type="button" onClick={onLogout} className="min-h-11 rounded-md px-3 text-sm text-muted hover:bg-surface2 hover:text-fg">Выйти</button>
    </div>
  </header>;
}
