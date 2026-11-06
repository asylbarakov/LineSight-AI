"use client";

import { useEffect, useState } from "react";
import { ApiError, getMetrics, listInspections } from "@/lib/api";
import type { InspectionSummary, Metrics } from "@/lib/types";

export function useDashboardData() {
  const [inspections, setInspections] = useState<InspectionSummary[] | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [errors, setErrors] = useState<{ inspections?: string; metrics?: string }>({});
  const [refreshing, setRefreshing] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const errorMessage = (reason: unknown) => reason instanceof ApiError ? reason.message : "Проверьте соединение с сервером.";
    const load = async () => {
      setRefreshing(true);
      // Independent failures must not hide the other API's usable data.
      const [list, summary] = await Promise.allSettled([listInspections(), getMetrics()]);
      if (!alive) return;
      if (list.status === "fulfilled") setInspections(list.value);
      if (summary.status === "fulfilled") setMetrics(summary.value);
      setErrors({
        inspections: list.status === "rejected" ? errorMessage(list.reason) : undefined,
        metrics: summary.status === "rejected" ? errorMessage(summary.reason) : undefined,
      });
      if (list.status === "fulfilled" || summary.status === "fulfilled") setUpdatedAt(new Date());
      setRefreshing(false);
      const unauthorized = [list, summary].some((result) => result.status === "rejected" && result.reason instanceof ApiError && result.reason.status === 401);
      if (unauthorized) return; // API client redirects to login.
      const active = list.status === "fulfilled" && list.value.some((row) => row.status === "queued" || row.status === "processing");
      timer = setTimeout(load, active ? 5000 : 30000);
    };
    void load();
    return () => { alive = false; clearTimeout(timer); };
  }, [revision]);

  return { inspections, metrics, errors, refreshing, updatedAt, refresh: () => setRevision((value) => value + 1) };
}
