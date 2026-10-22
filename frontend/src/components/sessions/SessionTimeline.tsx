import { Bot, ChevronRight, SlidersHorizontal, Terminal, User } from "lucide-react";
import type { InspectionSelection, TimelineItem } from "../../types/session";
import { formatCount } from "../../utils/format";
import { Payload } from "./SessionInspector";
import { HighlightedText } from "./HighlightedText";

function MessageContent({ data, query }: { data: Record<string, unknown>; query: string }) {
  const parts: unknown[] = Array.isArray(data.content) ? data.content : [];
  return (
    <div className="conversation-content">
      {typeof data.text === "string" && <p className="conversation-text"><HighlightedText text={data.text} query={query} /></p>}
      {parts.map((part, index) => {
        if (!part || typeof part !== "object") return <Payload key={index} label="Content" value={part} />;
        const content = part as Record<string, unknown>;
        if (content.type === "text" && typeof content.text === "string") {
          return <p className="conversation-text" key={index}><HighlightedText text={content.text} query={query} /></p>;
        }
        if (content.type === "reasoning") return <Payload key={index} label="Reasoning" value={content.text ?? content} />;
        if (content.type === "tool") return null;
        return <Payload key={index} label={`Content: ${String(content.type ?? "unknown")}`} value={content} />;
      })}
    </div>
  );
}

interface TimelineProps {
  items: TimelineItem[];
  selection?: InspectionSelection | null;
  onInspect?: (selection: InspectionSelection) => void;
  query?: string;
  searchTarget?: string | null;
}

export function Timeline({ items, selection, onInspect, query = "", searchTarget }: TimelineProps) {
  return (
    <ol className="conversation-list">
      {items.map((item) => {
        const isUser = item.kind === "user";
        const isAssistant = item.kind === "assistant";
        const label = isUser ? "You" : isAssistant ? "Assistant" : item.kind;
        const Icon = isUser ? User : Bot;
        return (
          <li key={item.id}>
            <article id={`session-message-${item.id}`} tabIndex={-1}
              className={`conversation-message${selection?.messageId === item.id ? " is-inspected" : ""}${searchTarget === item.id ? " is-search-target" : ""}`}>
              <header className="conversation-heading">
                <span className={`conversation-avatar${isUser ? " is-user" : ""}`}><Icon size={16} aria-hidden="true" /></span>
                <strong>{label}</strong>
                {item.model?.id && <span className="conversation-model">{item.model.id}</span>}
                <span className="conversation-time">{item.created_at ? new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Unknown time"}</span>
                <button
                  className="message-inspect-button"
                  type="button"
                  aria-label={`Inspect message ${item.sequence ?? item.id}`}
                  aria-pressed={selection?.messageId === item.id && !selection.toolId}
                  onClick={() => onInspect?.({ messageId: item.id })}
                >
                  <SlidersHorizontal size={14} aria-hidden="true" /><span>Inspect</span>
                </button>
              </header>
              <div className="conversation-message-body">
                {item.normalization_warnings?.map((warning) => <p className="session-warning" role="status" key={warning}>{warning}</p>)}
                {item.raw_data && <MessageContent data={item.raw_data} query={query} />}
                {item.raw_payload != null && <Payload label="Unrecognized native payload" value={item.raw_payload} />}
                {item.tools.length > 0 && <div className="conversation-tools">
                  {item.tools.map((tool) => (
                    <div className="conversation-tool" key={tool.id}>
                      <button
                        className="conversation-tool-button"
                        type="button"
                        aria-label={`Inspect ${tool.name ?? "Unknown tool"} execution`}
                        aria-pressed={selection?.messageId === item.id && selection.toolId === tool.id}
                        onClick={() => onInspect?.({ messageId: item.id, toolId: tool.id })}
                      >
                        <Terminal size={15} aria-hidden="true" />
                        <strong>{tool.name ?? "Unknown tool"}</strong>
                        <span className="tool-native-state">{tool.status ?? "Unknown"}</span>
                        <span className="tool-duration">{tool.duration_ms == null ? "—" : `${formatCount(tool.duration_ms)} ms`}</span>
                        <ChevronRight size={14} aria-hidden="true" />
                      </button>
                      {tool.exit_code != null && <small className="tool-exit-code">Exit code: {tool.exit_code}</small>}
                      {tool.child_session_id && <a className="tool-child-link" href={`#/sessions/${encodeURIComponent(tool.child_session_id)}`}>Open child session</a>}
                    </div>
                  ))}
                </div>}
                <footer className="conversation-footer">
                  <span>#{item.sequence ?? "Unknown order"}</span>
                  {item.usage && <span className="message-token-values">
                    <span className="token-generation">Input: {formatCount(item.usage.input_tokens)}</span>
                    <span className="token-generation">Output: {formatCount(item.usage.output_tokens)}</span>
                    <span className="token-cache">Cache read: {formatCount(item.usage.cache_read_tokens)}</span>
                    <span className="token-cache">Cache write: {formatCount(item.usage.cache_write_tokens)}</span>
                  </span>}
                </footer>
              </div>
            </article>
          </li>
        );
      })}
    </ol>
  );
}
