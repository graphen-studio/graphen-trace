import { Bot, ChevronRight, SlidersHorizontal, Terminal, User } from "lucide-react";
import type { InspectionSelection, TimelineItem } from "../../types/session";
import { formatCount } from "../../utils/format";
import { Payload } from "./SessionInspector";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownNode {
  type: string;
  value?: string;
  tagName?: string;
  properties?: Record<string, string[]>;
  children?: MarkdownNode[];
}

function highlightSearchTerm(query: string) {
  const term = query.trim();
  if (!term) return [];
  return [() => (tree: MarkdownNode) => {
    function visit(node: MarkdownNode) {
      if (!node.children) return;
      node.children = node.children.flatMap((child) => {
        if (child.type !== "text" || typeof child.value !== "string") {
          visit(child);
          return [child];
        }
        const pieces: MarkdownNode[] = [];
        let remaining = child.value;
        while (remaining.length > 0) {
          const index = remaining.toLocaleLowerCase().indexOf(term.toLocaleLowerCase());
          if (index < 0) {
            pieces.push({ type: "text", value: remaining });
            break;
          }
          if (index > 0) pieces.push({ type: "text", value: remaining.slice(0, index) });
          pieces.push({
            type: "element",
            tagName: "mark",
            properties: { className: ["session-search-highlight"] },
            children: [{ type: "text", value: remaining.slice(index, index + term.length) }],
          });
          remaining = remaining.slice(index + term.length);
        }
        return pieces;
      });
    }
    visit(tree);
  }];
}

export function MarkdownContent({ source, query = "" }: { source: string; query?: string }) {
  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={highlightSearchTerm(query)} skipHtml>
        {source}
      </ReactMarkdown>
    </div>
  );
}

function ReasoningContent({ value, query }: { value: unknown; query: string }) {
  if (value == null) return null;
  if (typeof value === "string" && value.trim().length === 0) return null;
  if (
    typeof value === "object"
    && !Array.isArray(value)
    && Object.keys(value).every((key) => key === "type")
  ) return null;
  if (typeof value !== "string") {
    return <Payload label="Reasoning" value={value} />;
  }
  return (
    <details className="source-payload reasoning-payload">
      <summary>Reasoning</summary>
      <MarkdownContent source={value} query={query} />
    </details>
  );
}

function MessageContent({ data, query }: { data: Record<string, unknown>; query: string }) {
  const parts: unknown[] = Array.isArray(data.content) ? data.content : [];
  return (
    <div className="conversation-content">
      {typeof data.text === "string" && <MarkdownContent source={data.text} query={query} />}
      {parts.map((part, index) => {
        if (!part || typeof part !== "object") return <Payload key={index} label="Content" value={part} />;
        const content = part as Record<string, unknown>;
        if (content.type === "text" && typeof content.text === "string") {
          return <MarkdownContent source={content.text} query={query} key={index} />;
        }
        if (content.type === "reasoning") return <ReasoningContent key={index} value={content.text ?? content} query={query} />;
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
