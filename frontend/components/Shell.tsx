"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { logout, USE_MOCKS } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { initialSidebarCollapsed } from "@/lib/layout";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const mobileNav = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let saved: string | null = null;
    try { saved = localStorage.getItem("ls_sidebar_collapsed"); } catch { /* session-only layout */ }
    setCollapsed(initialSidebarCollapsed(saved, window.innerWidth));
  }, []);
  function toggleSidebar() {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem("ls_sidebar_collapsed", String(next)); } catch { /* session-only layout */ }
  }
  useEffect(() => {
    if (!menuOpen) return;
    const trigger = document.activeElement as HTMLElement | null;
    mobileNav.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") { setMenuOpen(false); trigger?.focus(); } };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [menuOpen]);
  useEffect(() => setMenuOpen(false), [pathname]);

  // защита страниц: без токена — на /login
  useEffect(() => {
    if (!USE_MOCKS && !getToken()) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [router]);

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="app-shell min-h-screen" data-nav-collapsed={collapsed}>
      <a href="#main-content" className="sr-only z-50 rounded-lg bg-surface p-3 text-sm text-accent focus:not-sr-only focus:fixed focus:left-4 focus:top-4">К содержимому</a>
      <Sidebar pathname={pathname} collapsed={collapsed} onCollapse={toggleSidebar} />
      <Header pathname={pathname} menuOpen={menuOpen} onToggleMenu={() => setMenuOpen((open) => !open)} onLogout={onLogout} />
      <div ref={mobileNav} id="mobile-navigation" hidden={!menuOpen}><Sidebar pathname={pathname} mobile onNavigate={() => setMenuOpen(false)} /></div>
      {USE_MOCKS && <p role="status" className="border-b border-warn/30 bg-warn-soft px-5 py-2 text-xs text-warn">Демонстрационный режим · Все данные на этой странице являются примерами.</p>}
      <main id="main-content" className="mx-auto max-w-[1760px] px-4 py-4 md:px-5 md:py-5">{ready ? children : null}</main>
    </div>
  );
}
