import { Activity, Bot, Boxes, CircleDollarSign, Clock3, Radio, Search } from "lucide-react";
import { useEffect, useState } from "react";
import SessionDetails from "./SessionDetails";

function selectedSession(): string | null {
  const match = window.location.hash.match(/^#\/sessions\/([^/]+)$/);
  try { return match ? decodeURIComponent(match[1]) : null; }
  catch { return null; }
}

interface Session {
  id: string;
  title: string | null;
  updated_at: string | null;
  message_count: number | null;
  source: string;
  usage: { input_tokens: number | null; output_tokens: number | null };
}

interface Collection {
  state: string;
  detail: string;
  last_seen: string | null;
  warnings?: string[];
}

interface UsageSummary {
  session_count: number;
  generation_count: number | null;
  usage: Record<string, number | null>;
  usage_incomplete: string[];
  reported_cost: number | null;
  cost_incomplete: boolean;
}

const metrics = [
  { label: "Native input tokens", key: "input_tokens", icon: Activity, color: "blue" },
  { label: "Native output tokens", key: "output_tokens", icon: Radio, color: "cyan" },
  { label: "Reasoning tokens", key: "reasoning_tokens", icon: Bot, color: "green" },
  { label: "Cache read tokens", key: "cache_read_tokens", icon: Activity, color: "blue" },
  { label: "Cache write tokens", key: "cache_write_tokens", icon: Radio, color: "cyan" },
  { label: "Sessions", key: "sessions", icon: Bot, color: "green" },
  { label: "Agent-reported cost", key: "cost", icon: CircleDollarSign, color: "purple" },
];

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [collection, setCollection] = useState<Collection | null>(null);
  const [liveCollection, setLiveCollection] = useState<Collection | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState(selectedSession);

  useEffect(() => {
    const navigate = () => setSessionId(selectedSession());
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const responses = await Promise.all([
          fetch("/api/sessions", { signal: controller.signal }),
          fetch("/api/collection", { signal: controller.signal }),
          fetch("/api/usage", { signal: controller.signal }),
          fetch("/api/collection/live", { signal: controller.signal }),
        ]);
        if (responses.some((response) => !response.ok)) {
          throw new Error("Could not load collection data");
        }
        const [data, status, consumption, live] = await Promise.all(responses.map((response) => response.json()));
        if (!controller.signal.aborted) {
          setSessions(data.items);
          setCollection(status);
          setLiveCollection(live);
          setUsage(consumption);
          setError(null);
        }
      } catch {
        if (!controller.signal.aborted) setError("Local service unavailable. Displayed data may be stale.");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 2000);
      }
    }
    void refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <img src="/logo-without-text.png" alt="" />
          <span>Graphen <b>Trace</b></span>
        </div>
        <div className="connection">{error ? "Service unavailable" : "Local service"}</div>
      </header>

      <section className="intro">
        <div>
          <div className="eyebrow"><Activity size={14} /> AGENT OBSERVABILITY</div>
          <h1>Trace your work.</h1>
          <p>See what your coding agents are doing, as it happens.</p>
        </div>
        <button className="project-select"><Boxes size={16} /> All projects <span>⌄</span></button>
      </section>

      <section className="metrics">
        {metrics.map(({ label, key, icon: Icon, color }) => (
          <article className="metric" key={label}>
            <div className={`metric-icon ${color}`}><Icon size={18} /></div>
            <div><div className="metric-value">{usage ? (key === "sessions" ? usage.session_count : key === "cost" ? usage.reported_cost : usage.usage[key]) ?? "—" : "—"}</div><div className="metric-label">{label}{usage && (key === "cost" ? usage.cost_incomplete : usage.usage_incomplete.includes(key)) ? " (partial)" : ""}</div></div>
          </article>
        ))}
      </section>
      <p className="collection-state">Native token categories across all synchronized sessions; cache and reasoning are shown separately, without assuming provider totals. Cost currency/calculation are unverified, not confirmed billing.</p>
      {((collection?.warnings?.length ?? 0) > 0 || collection?.state === "unavailable") && <aside className="collection-state" role="status">
        <strong>Collection warning — captured data remains available</strong>
        {collection?.state === "unavailable" && <p>{collection.detail}</p>}
        <ul>{collection?.warnings?.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      </aside>}
      {(liveCollection?.state === "partial" || liveCollection?.state === "unavailable") && <aside className="collection-state" role="status">
        <strong>Live events: {liveCollection.state}</strong>
        <p>{liveCollection.detail}</p>
        <ul>{liveCollection.warnings?.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      </aside>}

      {sessionId ? <>
        <SessionDetails key={sessionId} sessionId={sessionId} />
        <p className="collection-state" role="status">{error || (collection ? `${collection.state}: ${collection.detail}` : "Connecting…")}</p>
      </> : <section className="sessions panel">
        <div className="section-heading">
          <div><h2>Sessions</h2><p>Your agent activity will appear here</p></div>
          <button className="filter"><Search size={15} /> Search sessions</button>
        </div>
        {sessions.length > 0 ? (
          <div className="session-list">
            {sessions.map((session) => (
              <article className="session-row" key={session.id}>
                <h3><a href={`#/sessions/${encodeURIComponent(session.id)}`}>{session.title || session.id}</a></h3>
                <p>{session.message_count ?? "—"} messages · Input: {session.usage.input_tokens ?? "—"} · Output: {session.usage.output_tokens ?? "—"}</p>
                <small>{session.source} · {session.updated_at ? new Date(session.updated_at).toLocaleString() : "Unknown update time"}</small>
              </article>
            ))}
          </div>
        ) : <div className="empty-state">
          <div className="empty-icon"><Clock3 size={22} /></div>
          <h3>Waiting for agent activity</h3>
          <p>Start OpenCode or run <code>graphen-trace discover</code> to check your setup.</p>
        </div>}
        <div className="collection-state" role="status">
          {error || (collection ? `${collection.state}: ${collection.detail}` : "Connecting to local service…")}
          {collection?.last_seen && <small>Last synchronized: {new Date(collection.last_seen).toLocaleString()}</small>}
        </div>
      </section>}
      <footer>Local-first observability <span>·</span> Your data stays on this machine</footer>
    </main>
  );
}
