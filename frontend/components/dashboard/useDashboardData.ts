"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, DATA_CHANGED_KEY, getMetrics, listInspections } from "@/lib/api";
import { mergeDashboardData, startDashboardPolling } from "@/lib/dashboard";
import type { InspectionSummary, Metrics } from "@/lib/types";

export function useDashboardData() {
  const [{inspections, metrics}, setData] = useState<{inspections: InspectionSummary[] | null; metrics: Metrics | null}>({inspections: null, metrics: null});
  const [errors, setErrors] = useState<{ inspections?: string; metrics?: string }>({});
  const [refreshing, setRefreshing] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const poller = useRef<ReturnType<typeof startDashboardPolling> | null>(null);

  useEffect(() => {
    let alive = true;
    const errorMessage = (reason: unknown) => reason instanceof ApiError ? reason.message : "Проверьте соединение с сервером.";
    const load = async () => {
      setRefreshing(true);
      // Independent failures must not hide the other API's usable data.
      const [list, summary] = await Promise.allSettled([listInspections(), getMetrics()]);
      if (!alive) return false;
      setData(previous => mergeDashboardData(previous, list, summary));
      setErrors({
        inspections: list.status === "rejected" ? errorMessage(list.reason) : undefined,
        metrics: summary.status === "rejected" ? errorMessage(summary.reason) : undefined,
      });
      if (list.status === "fulfilled" || summary.status === "fulfilled") setUpdatedAt(new Date());
      setRefreshing(false);
      const unauthorized = [list, summary].some((result) => result.status === "rejected" && result.reason instanceof ApiError && result.reason.status === 401);
      if (unauthorized) { poller.current?.stop(); return false; } // API client redirects to login.
      const active = list.status === "fulfilled" && list.value.some((row) => row.status === "queued" || row.status === "processing");
      return active || list.status === "rejected" || summary.status === "rejected";
    };
    const controller = startDashboardPolling(load, () => !document.hidden);
    poller.current = controller;
    const refresh = () => controller.refresh();
    const storage = (event: StorageEvent) => { if (event.key === DATA_CHANGED_KEY) refresh(); };
    window.addEventListener("focus", refresh);
    window.addEventListener(DATA_CHANGED_KEY, refresh);
    window.addEventListener("storage", storage);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      alive = false; controller.stop(); poller.current = null;
      window.removeEventListener("focus", refresh);
      window.removeEventListener(DATA_CHANGED_KEY, refresh);
      window.removeEventListener("storage", storage);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);

  return { inspections, metrics, errors, refreshing, updatedAt, refresh: () => poller.current?.refresh() };
}
