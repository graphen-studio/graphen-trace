export interface TokenUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
}

export interface SessionDetail {
  id: string;
  title: string | null;
  agent: string;
  directory: string | null;
  parent_id: string | null;
  version: string | null;
  model: Record<string, string> | null;
  source: string;
  message_count: number | null;
  usage: TokenUsage;
  usage_incomplete: string[];
  reported_cost: number | null;
  cost_incomplete: boolean;
  normalization_warnings: string[];
}

export interface ToolExecution {
  id: string;
  name: string | null;
  status: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  exit_code: number | null;
  child_session_id: string | null;
  input?: unknown;
  output?: unknown;
  error?: unknown;
  metadata?: Record<string, unknown>;
}

export interface TimelineItem {
  id: string;
  kind: string;
  sequence: number | null;
  created_at: string | null;
  completed_at?: string | null;
  interaction_id: string | null;
  interaction_source: string | null;
  model: Record<string, string> | null;
  finish: string | null;
  usage: TokenUsage | null;
  tools: ToolExecution[];
  source: string;
  raw_data?: Record<string, unknown>;
  source_record?: Record<string, unknown>;
  reported_cost?: number | null;
  raw_payload?: unknown;
  normalization_warnings?: string[];
}

export interface TimelinePage {
  items: TimelineItem[];
  total: number;
  offset: number;
}

export interface SessionSearchResult {
  message_id: string;
  kind: string;
  timeline_offset: number;
  excerpt: string;
}

export interface SessionSearchResponse {
  items: SessionSearchResult[];
  total: number;
}

export type InspectionSelection =
  | { messageId: string; toolId?: undefined }
  | { messageId: string; toolId: string };
