import Link from "next/link";
import { Icon, type IconName } from "./Icon";

export const NAV_ITEMS: { href: string; label: string; icon: IconName; demo?: boolean }[] = [
  { href: "/dashboard", label: "Обзор", icon: "overview" },
  { href: "/inspections", label: "Инспекции", icon: "video" },
  { href: "/metrics", label: "Метрики", icon: "metrics" },
  { href: "/sections", label: "Участки ЛЭП", icon: "sections", demo: true },
  { href: "/preview", label: "Макеты", icon: "preview", demo: true },
];
export function Sidebar({ pathname, mobile = false, collapsed, onCollapse, onNavigate }: {
  pathname: string; mobile?: boolean; collapsed?: boolean; onCollapse?: () => void; onNavigate?: () => void;
}) {
  const link = (item: typeof NAV_ITEMS[number]) => {
    const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
    return <Link key={item.href} href={item.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
      aria-label={`${item.label}${item.demo ? " — демо" : ""}`} title={item.label}
      className={`nav-link flex min-h-11 items-center gap-3 rounded-md px-3 text-sm ${active ? "bg-sidebar-active font-medium text-sidebar-fg" : "text-sidebar-muted hover:bg-sidebar-active/60 hover:text-sidebar-fg"}`}>
      <Icon name={item.icon} /><span className="nav-label">{item.label}</span>
    </Link>;
  };
  return <aside data-sidebar className={mobile ? "max-h-[calc(100svh-var(--header-height))] overflow-y-auto overscroll-contain border-b border-sidebar-line bg-sidebar p-3 text-sidebar-fg lg:hidden" : "desktop-sidebar fixed inset-y-0 left-0 z-40 hidden overflow-y-auto overscroll-contain flex-col border-r border-sidebar-line bg-sidebar px-3 text-sidebar-fg lg:flex"}>
    {!mobile && <Link href="/dashboard" aria-label="LineSight AI — обзор" className="flex h-[var(--header-height)] shrink-0 items-center gap-2.5 px-2">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-sidebar-line"><Icon name="video" size={16} /></span>
      <span className="nav-label whitespace-nowrap text-sm font-semibold">LineSight AI</span>
    </Link>}
    <nav aria-label="Основная навигация" className="shrink-0 space-y-1">{NAV_ITEMS.filter(item => !item.demo).map(link)}</nav>
    <nav aria-label="Демонстрационные страницы" className="mt-4 shrink-0 space-y-1 border-t border-sidebar-line pt-3">
      <p className="nav-caption px-3 pb-1 text-xs text-sidebar-muted">В разработке · демо</p>{NAV_ITEMS.filter(item => item.demo).map(link)}
    </nav>
    {!mobile && <div className="mt-auto shrink-0 border-t border-sidebar-line py-3">
      <button type="button" onClick={onCollapse} aria-label={collapsed ? "Развернуть боковую панель" : "Свернуть боковую панель"} aria-expanded={!collapsed}
        className="nav-link flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-sidebar-muted hover:bg-sidebar-active"><Icon name="panel" /><span className="nav-label text-sm">Свернуть</span></button>
    </div>}
  </aside>;
}
