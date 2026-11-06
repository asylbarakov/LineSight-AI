"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { parseTheme, resolveTheme, THEME_STORAGE_KEY, type Theme } from "@/lib/theme";

interface ThemeContextValue { theme: Theme | null; toggleTheme: () => void }
const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  // null on both server and first client render prevents hydration mismatches.
  const [theme, setTheme] = useState<Theme | null>(null);
  const preference = useRef<Theme | null>(null);
  const current = useRef<Theme | null>(null);

  const apply = useCallback((next: Theme) => {
    document.documentElement.setAttribute("data-theme", next);
    current.current = next;
    setTheme(next);
  }, []);

  useEffect(() => {
    try { preference.current = parseTheme(window.localStorage.getItem(THEME_STORAGE_KEY)); } catch { /* storage blocked */ }
    apply(resolveTheme(preference.current));
    const onStorage = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
      preference.current = parseTheme(event.newValue);
      apply(resolveTheme(preference.current));
    };
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("storage", onStorage);
    };
  }, [apply]);

  const toggleTheme = useCallback(() => {
    const active = current.current ?? parseTheme(document.documentElement.getAttribute("data-theme")) ?? "dark";
    const next = active === "dark" ? "light" : "dark";
    // Keep an explicit session preference even if localStorage is unavailable.
    preference.current = next;
    apply(next);
    try { window.localStorage.setItem(THEME_STORAGE_KEY, next); } catch { /* theme still works for this session */ }
  }, [apply]);

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider");
  return context;
}
