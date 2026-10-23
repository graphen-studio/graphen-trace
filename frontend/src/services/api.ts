import type {
  AgentInstallation,
  CollectionStatus,
  DashboardSnapshot,
  SessionSummary,
  UsageSummary,
  LiveCollectionStatus,
  AgentResourceList,
} from "../types/api";
import type { SessionDetail, SessionSearchResponse, TimelinePage } from "../types/session";

export function getAgentResources(signal?: AbortSignal): Promise<AgentResourceList> {
  return request<AgentResourceList>("/api/resources", { signal });
}

function errorDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(errorDetail).filter(Boolean).join("; ") || null;
  }
  if (detail && typeof detail === "object" && "msg" in detail && typeof detail.msg === "string") {
    return detail.msg;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(errorDetail(data?.detail) || `Request failed (${response.status})`);
  }
  return data as T;
}

export async function getAgentSelection(signal?: AbortSignal): Promise<{
  agents: AgentInstallation[];
  collection: CollectionStatus;
}> {
  const [agents, collection] = await Promise.all([
    request<{ items: AgentInstallation[] }>("/api/agents", { signal }),
    request<CollectionStatus>("/api/collection", { signal }),
  ]);
  return { agents: agents.items, collection };
}

export function startCollection(agent: string): Promise<CollectionStatus> {
  return request<CollectionStatus>("/api/collection", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ agent }),
  });
}

export async function getDashboardSnapshot(
  agent: string,
  signal?: AbortSignal,
): Promise<DashboardSnapshot> {
  const query = `?agent=${encodeURIComponent(agent)}`;
  const [sessions, collection, usage, liveCollection] = await Promise.all([
    request<{ items: SessionSummary[] }>(`/api/sessions${query}`, { signal }),
    request<CollectionStatus>("/api/collection", { signal }),
    request<UsageSummary>(`/api/usage${query}`, { signal }),
    request<LiveCollectionStatus>(`/api/collection/live${query}`, { signal }),
  ]);
  return {
    sessions: sessions.items,
    collection,
    usage,
    liveCollection,
  };
}

export async function getSessionSnapshot(
  sessionId: string,
  page: number | null,
  signal: AbortSignal,
  agent = "opencode",
): Promise<{ session: SessionDetail; timeline: TimelinePage }> {
  const path = `/api/sessions/${encodeURIComponent(sessionId)}`;
  const query = agent === "opencode" ? "" : `?agent=${encodeURIComponent(agent)}`;
  const [session, timeline] = await Promise.all([
    request<SessionDetail>(`${path}${query}`, { signal }),
    request<TimelinePage>(`${path}/timeline?limit=50&${page == null ? "latest=true" : `offset=${page * 50}`}${query ? `&${query.slice(1)}` : ""}`, { signal }),
  ]);
  if (!Number.isInteger(timeline.offset) || timeline.offset < 0) {
    throw new Error("Session pagination requires the updated API. Restart graphen-trace serve and reload this page.");
  }
  return { session, timeline };
}

export function searchSession(
  sessionId: string,
  query: string,
  offset: number,
  signal: AbortSignal,
  agent = "opencode",
): Promise<SessionSearchResponse> {
  const params = new URLSearchParams({ q: query, limit: "20", offset: String(offset) });
  if (agent !== "opencode") params.set("agent", agent);
  return request<SessionSearchResponse>(`/api/sessions/${encodeURIComponent(sessionId)}/search?${params}`, { signal });
}
