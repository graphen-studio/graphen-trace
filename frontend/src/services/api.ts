import type {
  AgentInstallation,
  CollectionStatus,
  DashboardSnapshot,
  SessionSummary,
  UsageSummary,
  LiveCollectionStatus,
} from "../types/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status})`);
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
