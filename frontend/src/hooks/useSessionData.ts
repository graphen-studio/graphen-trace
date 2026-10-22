import { useEffect, useState } from "react";
import { getSessionSnapshot } from "../services/api";
import type { SessionDetail, TimelinePage } from "../types/session";

export function useSessionData(sessionId: string, page: number | null) {
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelinePage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setTimeline(null);
    setError(null);
    // Resolve the initial latest page once; polling must not move the reader.
    let resolvedPage = page;

    async function refresh() {
      try {
        const snapshot = await getSessionSnapshot(sessionId, resolvedPage, controller.signal);
        if (!controller.signal.aborted) {
          resolvedPage = Math.floor(snapshot.timeline.offset / 50);
          setSession(snapshot.session);
          setTimeline(snapshot.timeline);
          setError(null);
        }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "Local service unavailable.");
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
  }, [sessionId, page]);

  return { session, timeline, error };
}
