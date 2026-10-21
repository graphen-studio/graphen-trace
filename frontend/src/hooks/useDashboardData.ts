import { useEffect, useState } from "react";
import { getDashboardSnapshot } from "../services/api";
import type { DashboardSnapshot } from "../types/api";

export function useDashboardData(active: boolean, agent: string | null) {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active || !agent) return;
    const selectedAgent = agent;

    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setData(null);
    setError(null);

    async function refresh() {
      try {
        const snapshot = await getDashboardSnapshot(selectedAgent, controller.signal);
        if (!controller.signal.aborted) {
          setData(snapshot);
          setError(null);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError("Local service unavailable. Displayed data may be stale.");
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 2000);
      }
    }

    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [active, agent]);

  return { data, error };
}
