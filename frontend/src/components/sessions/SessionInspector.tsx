import { ArrowUpRight, X } from "lucide-react";
import type { SessionDetail, TimelineItem, TokenUsage, ToolExecution } from "../../types/session";
import { formatCost, formatCount } from "../../utils/format";
import { Payload } from "./Payload";
export { Payload } from "./Payload";

export function UsageDetails({ usage }: { usage: TokenUsage }) {
  return (
    <dl className="inspector-fields inspector-usage">
      <dt>Input tokens</dt><dd className="inspect-blue">{formatCount(usage.input_tokens)}</dd>
      <dt>Output tokens</dt><dd className="inspect-blue">{formatCount(usage.output_tokens)}</dd>
      <dt>Reasoning</dt><dd className="inspect-blue">{formatCount(usage.reasoning_tokens)}</dd>
      <dt>Cache read</dt><dd className="inspect-cyan">{formatCount(usage.cache_read_tokens)}</dd>
      <dt>Cache write</dt><dd className="inspect-cyan">{formatCount(usage.cache_write_tokens)}</dd>
    </dl>
  );
}

function DateValue({ value }: { value: string | null | undefined }) {
  return <>{value ? new Date(value).toLocaleString() : "—"}</>;
}

interface InspectorProps {
  session: SessionDetail;
  message: TimelineItem | null;
  tool: ToolExecution | null;
  onClose: () => void;
  onSession: () => void;
}

export default function SessionInspector({ session, message, tool, onClose, onSession }: InspectorProps) {
  const heading = tool ? "Tool execution" : message ? "Message details" : "Session details";
  return (
    <aside className={`session-inspector panel${tool ? " inspecting-tool" : ""}`} id="session-inspector" aria-label="Technical inspection">
      <header className="inspector-heading">
        <div><span className="inspector-eyebrow">INSPECT</span><h2>{heading}</h2></div>
        <button className="topbar-icon-button" type="button" onClick={onClose} aria-label="Close inspection panel">
          <X size={16} />
        </button>
      </header>
      <div className="inspector-body">
        {(tool || message) && <button className="inspector-back" type="button" onClick={onSession}>← Session details</button>}
        {tool ? (
          <>
            <h3 className="inspector-title">{tool.name ?? "Unknown tool"}</h3>
            <dl className="inspector-fields">
              <dt>Status</dt><dd><span className="inspector-state">{tool.status ?? "Unknown"}</span></dd>
              <dt>Duration</dt><dd className="inspect-purple">{tool.duration_ms == null ? "—" : `${formatCount(tool.duration_ms)} ms`}</dd>
              <dt>Exit code</dt><dd className={tool.exit_code != null && tool.exit_code !== 0 ? "inspect-warning" : undefined}>{tool.exit_code ?? "—"}</dd>
              <dt>Started</dt><dd><DateValue value={tool.started_at} /></dd>
              <dt>Completed</dt><dd><DateValue value={tool.completed_at} /></dd>
            </dl>
            <p className="inspector-note">Native execution state; completed does not necessarily mean the command succeeded.</p>
            <Payload label="Arguments" value={tool.input} />
            <Payload label="Result" value={tool.output} />
            <Payload label="Error" value={tool.error} />
            <Payload label="Tool metadata" value={tool.metadata} />
            {tool.child_session_id && <a className="inspector-link" href={`#/sessions/${encodeURIComponent(tool.child_session_id)}`}>Open child session <ArrowUpRight size={13} /></a>}
            <dl className="inspector-fields inspector-identifiers">
              <dt>Call ID</dt><dd>{tool.id}</dd>
              <dt>Message</dt><dd>{message?.id ?? "—"}</dd>
            </dl>
          </>
        ) : message ? (
          <>
            <h3 className="inspector-title">{message.kind}</h3>
            <dl className="inspector-fields">
              <dt>Model</dt><dd className="inspect-blue">{message.model?.id ?? "—"}</dd>
              <dt>Provider</dt><dd className="inspect-blue">{message.model?.providerID ?? "—"}</dd>
              <dt>Created</dt><dd><DateValue value={message.created_at} /></dd>
              <dt>Completed</dt><dd><DateValue value={message.completed_at} /></dd>
              <dt>Finish</dt><dd>{message.finish ?? "—"}</dd>
            </dl>
            {message.usage && <UsageDetails usage={message.usage} />}
            {message.reported_cost != null && <p className="inspector-note">Agent-reported cost: {formatCost(message.reported_cost)} · Currency/calculation unverified.</p>}
            <dl className="inspector-fields inspector-identifiers">
              <dt>Message ID</dt><dd>{message.id}</dd>
              <dt>Sequence</dt><dd>{message.sequence ?? "Unknown order"}</dd>
              <dt>Interaction</dt><dd>{message.interaction_id ?? "—"}</dd>
              <dt>Association</dt><dd>{message.interaction_source ?? "—"}</dd>
              <dt>Source</dt><dd>{message.source}</dd>
            </dl>
            <Payload label="Complete native message" value={message.raw_data} />
            <Payload label="Unrecognized native payload" value={message.raw_payload} />
            <Payload label="Source record" value={message.source_record} />
          </>
        ) : (
          <>
            <p className="inspector-note">Select a message or tool in the conversation to inspect its technical data.</p>
            <dl className="inspector-fields">
              <dt>Project</dt><dd>{session.directory ?? "—"}</dd>
              <dt>Model (latest)</dt><dd className="inspect-blue">{session.model?.id ?? "—"}</dd>
              <dt>Provider</dt><dd className="inspect-blue">{session.model?.providerID ?? "—"}</dd>
              <dt>Agent version</dt><dd>{session.version ?? "—"}</dd>
              <dt>Messages</dt><dd>{formatCount(session.message_count)}</dd>
            </dl>
            <UsageDetails usage={session.usage} />
            <p className="inspector-note">Native token categories are separate. Missing values are not treated as zero.</p>
            <dl className="inspector-fields inspector-identifiers">
              <dt>Session ID</dt><dd>{session.id}</dd>
              <dt>Source</dt><dd>{session.source}</dd>
            </dl>
            {session.parent_id && <a className="inspector-link" href={`#/sessions/${encodeURIComponent(session.parent_id)}`}>Open parent session <ArrowUpRight size={13} /></a>}
            <p className="inspector-note">Local capture may include private code or secrets. Only data exposed by the source is available.</p>
          </>
        )}
      </div>
    </aside>
  );
}
