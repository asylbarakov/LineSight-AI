"use client";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

/** Serial polling, stale-result guard and last-good-data retention, with an explicit retry. */
export function useResource<T>(load: () => Promise<T>, interval = 0) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      setLoading(true);
      let unauthorized = false;
      try {
        const result = await load();
        if (alive) { setData(result); setError(null); }
      } catch (reason) {
        unauthorized = reason instanceof ApiError && reason.status === 401;
        if (alive) setError(reason instanceof Error ? reason.message : "Не удалось загрузить данные.");
      } finally {
        if (alive) {
          setLoading(false);
          if (interval && !unauthorized) timer = setTimeout(tick, interval);
        }
      }
    };
    void tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [load, interval, revision]);
  return { data, loading, error, retry: () => setRevision(value => value + 1) };
}
