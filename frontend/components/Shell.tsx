"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { logout, USE_MOCKS } from "@/lib/api";
import { getToken } from "@/lib/auth";

const NAV = [
  { href: "/inspections", label: "Инспекции" },
  { href: "/metrics", label: "Метрики" },
  { href: "/preview", label: "Макеты" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

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
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-8 px-6">
          <Link href="/inspections" className="flex items-center gap-2 text-base font-semibold tracking-tight">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-accent" />
            LineSight AI
          </Link>
          <nav className="flex gap-1">
            {NAV.map((n) => {
              const active = pathname === n.href || pathname.startsWith(n.href + "/");
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                    active ? "bg-surface2 text-fg" : "text-muted hover:text-fg"
                  }`}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto">
            <button onClick={onLogout} className="rounded-md px-3 py-1.5 text-sm text-muted hover:text-fg">
              Выйти
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{ready ? children : null}</main>
    </div>
  );
}
