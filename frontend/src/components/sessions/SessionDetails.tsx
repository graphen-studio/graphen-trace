import { ArrowLeft, ChevronLeft, ChevronRight, Folder, PanelRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useSessionData } from "../../hooks/useSessionData";
import type { InspectionSelection, SessionSearchResult } from "../../types/session";
import { formatCost, formatCount } from "../../utils/format";
import SessionInspector from "./SessionInspector";
import { Timeline } from "./SessionTimeline";
import SessionSearch from "./SessionSearch";

export { Payload } from "./SessionInspector";
export { Timeline } from "./SessionTimeline";
export type { TimelineItem } from "../../types/session";

export default function SessionDetails({
  sessionId,
  agent,
}: {
  sessionId: string;
  agent: string;
}) {
  const [page, setPage] = useState<number | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(() => window.innerWidth > 1200);
  const [selection, setSelection] = useState<InspectionSelection | null>(null);
  const [query, setQuery] = useState("");
  const [scrollTarget, setScrollTarget] = useState<string | null>(null);
  const [searchTarget, setSearchTarget] = useState<string | null>(null);
  const { session, timeline, error } = useSessionData(sessionId, page, agent);
  const currentPage = timeline ? Math.floor(timeline.offset / 50) : page ?? 0;
  const lastPage = timeline ? Math.max(0, Math.ceil(timeline.total / 50) - 1) : 0;
  const message = timeline?.items.find((item) => item.id === selection?.messageId) ?? null;
  const tool = message?.tools.find((item) => item.id === selection?.toolId) ?? null;

  useEffect(() => {
    if (!scrollTarget || !timeline?.items.some((item) => item.id === scrollTarget)) return;
    const element = document.getElementById(`session-message-${scrollTarget}`);
    if (element) {
      element.scrollIntoView({ block: "center" });
      element.focus({ preventScroll: true });
      setScrollTarget(null);
    }
  }, [scrollTarget, timeline]);

  useEffect(() => {
    if (!inspectorOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setInspectorOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [inspectorOpen]);

  function inspect(next: InspectionSelection) {
    setSelection(next);
    setInspectorOpen(true);
  }

  function changePage(next: number) {
    setSelection(null);
    setScrollTarget(null);
    setPage(next);
  }

  function openSearchResult(result: SessionSearchResult) {
    setSelection(null);
    setPage(Math.floor(result.timeline_offset / 50));
    setSearchTarget(result.message_id);
    setScrollTarget(result.message_id);
  }

  const metrics = session ? [
    { label: "Input tokens", tone: "blue", value: formatCount(session.usage.input_tokens), partial: session.usage_incomplete.includes("input_tokens") },
    { label: "Output tokens", tone: "blue", value: formatCount(session.usage.output_tokens), partial: session.usage_incomplete.includes("output_tokens") },
    { label: "Reasoning", tone: "blue", value: formatCount(session.usage.reasoning_tokens), partial: session.usage_incomplete.includes("reasoning_tokens") },
    { label: "Cache read", tone: "cyan", value: formatCount(session.usage.cache_read_tokens), partial: session.usage_incomplete.includes("cache_read_tokens") },
    { label: "Cache write", tone: "cyan", value: formatCount(session.usage.cache_write_tokens), partial: session.usage_incomplete.includes("cache_write_tokens") },
    { label: "Reported cost", tone: "green", value: formatCost(session.reported_cost), partial: session.cost_incomplete },
  ] : [];

  return (
    <section className="session-explorer" aria-label="Session explorer">
      <header className="session-header">
        <a className="session-back" href="#" aria-label="Back to all sessions">
          <span className="session-back-icon"><ArrowLeft size={16} aria-hidden="true" /></span>
          <span className="session-back-copy">All sessions</span>
        </a>
        <div className="session-title-row">
          <div>
            <span className="inspector-eyebrow">SESSION EXPLORER</span>
            <h1>{session?.title || sessionId}</h1>
          </div>
          <button
            className="topbar-button"
            type="button"
            aria-expanded={inspectorOpen}
            aria-controls="session-inspector"
            onClick={() => setInspectorOpen((open) => !open)}
          >
            <PanelRight size={16} /> Details
          </button>
        </div>
        <p className="session-project"><Folder size={14} />{session?.directory ?? "Project unavailable"}</p>
      </header>

      {session && <>
        <dl className="session-summary panel" aria-label="Session consumption">
          {metrics.map((metric) => <div className={`summary-tone-${metric.tone}`} key={metric.label}>
            <dt>{metric.label}{metric.partial && <span className="metric-partial"> · partial</span>}</dt>
            <dd>{metric.value}</dd>
          </div>)}
        </dl>
        <p className="session-summary-note">This session only · Native token categories shown separately · Reported cost is not verified billing; currency/calculation unverified.</p>
        {session.normalization_warnings.map((warning) => <p className="session-warning" role="status" key={warning}>{warning}</p>)}
      </>}

      {error && <p className="session-warning" role="alert">{error}</p>}
      <div className={`session-workspace${inspectorOpen && session ? " with-inspector" : ""}`}>
        <div className="conversation-panel panel">
          <div className="conversation-panel-heading">
            <h2>Conversation</h2>
            <div className="conversation-navigation">
              <span>{timeline ? `${formatCount(timeline.total)} records` : "Loading…"}</span>
              <button className="topbar-button" type="button" disabled={!timeline || currentPage === 0} onClick={() => changePage(0)}>Go to beginning</button>
              <button className="topbar-button" type="button" disabled={!timeline || currentPage === lastPage} onClick={() => changePage(lastPage)}>Go to latest</button>
            </div>
          </div>
          <SessionSearch sessionId={sessionId} agent={agent} query={query} onQueryChange={(value) => {
            setQuery(value);
            setSearchTarget(null);
            setScrollTarget(null);
          }} onResult={openSearchResult} />
          {timeline ? <>
            <Timeline items={timeline.items} selection={selection} onInspect={inspect} query={query} searchTarget={searchTarget} />
            {timeline.total === 0 && <div className="session-conversation-empty">No messages have been synchronized for this session.</div>}
            <nav className="session-pagination" aria-label="Timeline pages">
              <button className="topbar-button" type="button" disabled={currentPage === 0} onClick={() => changePage(currentPage - 1)}><ChevronLeft size={14} /> Previous</button>
              <span>Page {formatCount(currentPage + 1)} of {formatCount(lastPage + 1)}</span>
              <button className="topbar-button" type="button" disabled={currentPage === lastPage} onClick={() => changePage(currentPage + 1)}>Next <ChevronRight size={14} /></button>
            </nav>
          </> : <p className="session-conversation-empty" role="status">{error ? "Session data unavailable." : "Loading conversation…"}</p>}
        </div>
        {inspectorOpen && session && <SessionInspector
          session={session}
          message={message}
          tool={tool}
          onClose={() => setInspectorOpen(false)}
          onSession={() => setSelection(null)}
        />}
      </div>
    </section>
  );
}
