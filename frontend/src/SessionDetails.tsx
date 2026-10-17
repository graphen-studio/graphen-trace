import { useEffect, useState } from "react";

interface Usage {
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
}

interface Session {
  id: string;
  title: string | null;
  directory: string | null;
  parent_id: string | null;
  version: string | null;
  source: string;
  usage: Usage;
  usage_incomplete: string[];
  reported_cost: number | null;
  cost_incomplete: boolean;
  raw_data: Record<string, unknown>;
}

interface Tool {
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
  sequence: number;
  created_at: string | null;
  interaction_id: string | null;
  interaction_source: string | null;
  model: Record<string, string> | null;
  finish: string | null;
  usage: Usage | null;
  tools: Tool[];
  source: string;
  raw_data?: Record<string, unknown>;
  source_record?: Record<string, unknown>;
  reported_cost?: number | null;
}

function UsageValues({ usage }: { usage: Usage }) {
  return <p>
    Input: {usage.input_tokens ?? "—"} · Output: {usage.output_tokens ?? "—"}
    {" · "}Reasoning: {usage.reasoning_tokens ?? "—"}
    {" · "}Cache read: {usage.cache_read_tokens ?? "—"}
    {" · "}Cache write: {usage.cache_write_tokens ?? "—"}
  </p>;
}

export function Payload({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null;
  return <details className="source-payload">
    <summary>{label}</summary>
    <pre>{typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>
  </details>;
}

function MessageContent({ data }: { data: Record<string, unknown> }) {
  const parts = Array.isArray(data.content) ? data.content : [];
  return <div className="message-content">
    {typeof data.text === "string" && <pre>{data.text}</pre>}
    {parts.map((part: Record<string, unknown>, index: number) => {
      if (!part || typeof part !== "object") return <Payload key={index} label="Content" value={part} />;
      if (part.type === "text" && typeof part.text === "string") return <pre key={index}>{part.text}</pre>;
      if (part.type === "reasoning") return <Payload key={index} label="Reasoning" value={part.text ?? part} />;
      if (part.type === "tool") return null;
      return <Payload key={index} label={`Content: ${String(part.type ?? "unknown")}`} value={part} />;
    })}
  </div>;
}

export function Timeline({ items }: { items: TimelineItem[] }) {
  return <ol className="timeline-list">
    {items.map((item) => <li className="session-row" key={item.id}>
      <h3>#{item.sequence} · {item.kind}</h3>
      <p>{item.created_at ? new Date(item.created_at).toLocaleString() : "Unknown time"}</p>
      {item.model && <p>Model: {item.model.providerID} / {item.model.id}</p>}
      {item.finish && <p>Finish: {item.finish}</p>}
      {item.usage && <UsageValues usage={item.usage} />}
      {item.reported_cost != null && <p>Agent-reported cost: {item.reported_cost} (currency/calculation unverified)</p>}
      {item.raw_data && <MessageContent data={item.raw_data} />}
      {item.interaction_id && <small>
        Interaction: {item.interaction_id} (associated by {item.interaction_source})
      </small>}
      {item.tools.map((tool) => <div className="tool-execution" key={tool.id}>
        <strong>{tool.name ?? "Unknown tool"}</strong>
        <p>Status: {tool.status ?? "Unknown"} · Duration: {tool.duration_ms == null ? "—" : `${tool.duration_ms} ms`}
          {" · "}Exit code: {tool.exit_code ?? "—"}</p>
        <small>Call ID: {tool.id}</small>
        <Payload label="Arguments" value={tool.input} />
        <Payload label="Result" value={tool.output} />
        <Payload label="Error" value={tool.error} />
        <Payload label="Tool metadata" value={tool.metadata} />
        {tool.child_session_id && <p><a href={`#/sessions/${encodeURIComponent(tool.child_session_id)}`}>Open child session</a></p>}
      </div>)}
      <small>Source: {item.source} · Message: {item.id}</small>
      <Payload label="Complete native message" value={item.raw_data} />
      <Payload label="Source record" value={item.source_record} />
    </li>)}
  </ol>;
}

export default function SessionDetails({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<Session | null>(null);
  const [timeline, setTimeline] = useState<{ items: TimelineItem[]; total: number } | null>(null);
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 50;

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setTimeline(null);
    setError(null);
    async function refresh() {
      try {
        const path = `/api/sessions/${encodeURIComponent(sessionId)}`;
        const responses = await Promise.all([
          fetch(path, { signal: controller.signal }),
          fetch(`${path}/timeline?limit=${pageSize}&offset=${page * pageSize}`, { signal: controller.signal }),
        ]);
        if (responses.some((response) => response.status === 404)) throw new Error("Session not found or not synchronized yet.");
        if (responses.some((response) => !response.ok)) throw new Error("Could not load session. Displayed data may be stale.");
        const [details, events] = await Promise.all(responses.map((response) => response.json()));
        if (!controller.signal.aborted) {
          setSession(details);
          setTimeline(events);
          setError(null);
        }
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Local service unavailable.");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 2000);
      }
    }
    void refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [sessionId, page]);

  return <section className="sessions panel">
    <div className="section-heading">
      <div><a href="#">← Back to sessions</a><h2>{session?.title || sessionId}</h2></div>
    </div>
    <div className="collection-state">
      <p>Full local capture. Content may include private code or secrets. Only data exposed by the source is available.</p>
      {session && <>
        <p>Directory: {session.directory ?? "Unknown"} · OpenCode: {session.version ?? "Unknown"}</p>
        <UsageValues usage={session.usage} />
        {session.usage_incomplete.length > 0 && <p>Partial totals: {session.usage_incomplete.join(", ")}. Missing values are not treated as zero.</p>}
        {session.reported_cost != null && <p>Agent-reported cost: {session.reported_cost}{session.cost_incomplete ? " (partial)" : ""} · Currency/calculation unverified; not confirmed billing.</p>}
        <small>Source: {session.source}</small>
        <Payload label="Complete native session" value={session.raw_data} />
        {session.parent_id && <p><a href={`#/sessions/${encodeURIComponent(session.parent_id)}`}>Open parent session</a></p>}
      </>}
      {error && <p role="alert">{error}</p>}
      {!timeline && !error && <p role="status">Loading session…</p>}
    </div>
    {timeline && <>
      <Timeline items={timeline.items} />
      {timeline.total === 0 && <p className="collection-state">No timeline records have been synchronized.</p>}
      <nav className="timeline-pagination" aria-label="Timeline pages">
        <button className="filter" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
        <span>{timeline.total} records · Page {page + 1}</span>
        <button className="filter" disabled={(page + 1) * pageSize >= timeline.total} onClick={() => setPage(page + 1)}>Next</button>
      </nav>
    </>}
  </section>;
}
