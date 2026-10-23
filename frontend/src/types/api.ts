export interface AgentInstallation {
  name: string;
  path: string;
  version: string | null;
  adapter: boolean;
}

export interface AgentSkill {
  name: string;
  description: string;
  scope: "project" | "global";
  path: string;
  content: string;
  agents: { id: string; name: string }[];
}

export interface AgentResourceList {
  items: AgentSkill[];
}

export interface CollectionStatus {
  state: string;
  detail: string;
  agent: string | null;
  last_seen: string | null;
  warnings?: string[];
}

export interface SessionSummary {
  id: string;
  title: string | null;
  directory: string | null;
  model: Record<string, string> | null;
  updated_at: string | null;
  message_count: number | null;
  source: string;
  usage: {
    input_tokens: number | null;
    output_tokens: number | null;
  };
}

export interface UsageSummary {
  session_count: number;
  generation_count: number | null;
  usage: Record<string, number | null>;
  usage_incomplete: string[];
  reported_cost: number | null;
  cost_incomplete: boolean;
}

export interface LiveCollectionStatus {
  state: string;
  detail: string;
  warnings?: string[];
}

export interface DashboardSnapshot {
  sessions: SessionSummary[];
  collection: CollectionStatus;
  usage: UsageSummary;
  liveCollection: LiveCollectionStatus;
}
