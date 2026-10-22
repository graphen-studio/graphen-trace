import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { searchSession } from "../../services/api";
import type { SessionSearchResponse, SessionSearchResult } from "../../types/session";
import { formatCount } from "../../utils/format";
import { HighlightedText } from "./HighlightedText";

interface SessionSearchProps {
  sessionId: string;
  query: string;
  onQueryChange: (query: string) => void;
  onResult: (result: SessionSearchResult) => void;
}

export default function SessionSearch({ sessionId, query, onQueryChange, onResult }: SessionSearchProps) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<SessionSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const term = query.trim();

  useEffect(() => {
    setData(null);
    setError(null);
    if (!term) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const result = await searchSession(sessionId, term, offset, controller.signal);
        if (!controller.signal.aborted) setData(result);
      } catch {
        if (!controller.signal.aborted) setError("Could not search this session. Try again.");
      }
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [sessionId, term, offset]);

  function changeQuery(value: string) {
    setOffset(0);
    setData(null);
    onQueryChange(value);
  }

  return <div className="session-search-area">
    <label className="session-search-input">
      <Search size={15} aria-hidden="true" />
      <input type="search" value={query} maxLength={200}
        placeholder="Search prompts and responses in this session"
        aria-label="Search all prompts and responses in this session"
        onChange={(event) => changeQuery(event.target.value)} />
      {query && <button type="button" onClick={() => changeQuery("")} aria-label="Clear session search"><X size={14} /></button>}
    </label>
    {term && <div className="session-search-results">
      <div className="session-search-result-heading" role="status">
        {error || (data ? `${formatCount(data.total)} matching messages across this session` : "Searching all messages…")}
      </div>
      {data?.items.map((result) => <button type="button" className="session-search-result"
        key={result.message_id} onClick={() => onResult(result)}>
        <span>{result.kind === "user" ? "You" : "Assistant"} <ChevronRight size={12} /></span>
        <p><HighlightedText text={result.excerpt} query={term} /></p>
      </button>)}
      {data && data.total > 20 && <div className="session-search-result-pages">
        <button className="topbar-icon-button" type="button" disabled={offset === 0} onClick={() => setOffset(offset - 20)} aria-label="Previous search results"><ChevronLeft size={14} /></button>
        <span>{formatCount(offset + 1)}–{formatCount(Math.min(offset + 20, data.total))} of {formatCount(data.total)}</span>
        <button className="topbar-icon-button" type="button" disabled={offset + 20 >= data.total} onClick={() => setOffset(offset + 20)} aria-label="Next search results"><ChevronRight size={14} /></button>
      </div>}
    </div>}
  </div>;
}
