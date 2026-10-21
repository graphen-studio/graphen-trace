import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { SessionSummary } from "../../types/api";
import { formatCount } from "../../utils/format";

function formatUpdatedAt(value: string | null): string {
  if (!value) return "Unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export default function SessionTable({ sessions }: { sessions: SessionSummary[] }) {
  const [query, setQuery] = useState("");
  const filteredSessions = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) return sessions;
    return sessions.filter((session) =>
      [session.title, session.id, session.directory, session.model?.id]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase().includes(normalizedQuery)),
    );
  }, [query, sessions]);

  return <section className="sessions panel">
    <div className="section-heading">
      <div><h2>Sessions</h2><p>Latest observed agent sessions</p></div>
      <label className="session-search">
        <Search size={15} aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search title, project, or model"
          aria-label="Search sessions by title, project, or model"
        />
      </label>
    </div>
    {filteredSessions.length > 0 ? <div className="session-table-scroll">
      <table className="session-table">
        <thead><tr>
          <th scope="col">Session</th>
          <th scope="col">Model</th>
          <th scope="col" className="numeric">Messages</th>
          <th scope="col" className="numeric">Input tokens</th>
          <th scope="col" className="numeric">Output tokens</th>
          <th scope="col">Last updated</th>
        </tr></thead>
        <tbody>{filteredSessions.map((session) => <tr key={session.id}>
          <td className="session-name-cell">
            <a href={`#/sessions/${encodeURIComponent(session.id)}`}>
              {session.title || session.id}
            </a>
            <small title={session.directory ?? undefined}>
              {session.directory || session.id} · {session.source}
            </small>
          </td>
          <td>{session.model?.id ?? "—"}</td>
          <td className="numeric">{formatCount(session.message_count)}</td>
          <td className="numeric">{formatCount(session.usage.input_tokens)}</td>
          <td className="numeric">{formatCount(session.usage.output_tokens)}</td>
          <td>{formatUpdatedAt(session.updated_at)}</td>
        </tr>)}</tbody>
      </table>
    </div> : <div className="empty-state session-empty">
      <div className="empty-icon"><Search size={20} /></div>
      <h3>{query ? "No matching sessions" : "Waiting for agent activity"}</h3>
      <p>{query ? "Try a different title, project, or model." : "Observed sessions will appear here."}</p>
    </div>}
    <div className="collection-state">
      Showing {formatCount(filteredSessions.length)} of {formatCount(sessions.length)} loaded sessions
    </div>
  </section>;
}
