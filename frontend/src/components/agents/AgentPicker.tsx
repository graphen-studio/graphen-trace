import { Activity, Bot, Clock3 } from "lucide-react";
import type { AgentInstallation } from "../../types/api";
import { agentLabel } from "../../utils/agentLabel";

interface AgentPickerProps {
  agents: AgentInstallation[];
  error: string | null;
  selectingAgent: string | null;
  selectedAgent: string | null;
  onSelect: (agent: AgentInstallation) => void;
}

export default function AgentPicker({
  agents,
  error,
  selectingAgent,
  selectedAgent,
  onSelect,
}: AgentPickerProps) {
  return (
    <section className="agent-selection">
      <div className="intro">
        <div>
          <div className="eyebrow"><Activity size={14} /> AGENT OBSERVABILITY</div>
          <h1>Choose an agent.</h1>
          <p>
            {selectedAgent
              ? `Currently collecting with ${agentLabel(selectedAgent)}. Select another supported agent to switch.`
              : "Select an installed, supported coding agent to start passive collection."}
          </p>
        </div>
        <span className="selection-note">
          {selectedAgent
            ? "The current collector stays active until you select another agent."
            : "No agent is collecting yet."}
        </span>
      </div>

      {error && <p className="selection-error" role="alert">{error}</p>}

      {agents.length > 0 ? (
        <div className="agent-grid">
          {agents.map((agent) => {
            const isSelected = selectedAgent === agent.name;
            const isStarting = selectingAgent === agent.name;
            return (
              <article
                className={`agent-card${agent.adapter ? " supported" : " unsupported"}${isSelected ? " selected" : ""}`}
                key={agent.name}
              >
                <div className="agent-card-heading">
                  <div className="agent-icon"><Bot size={21} /></div>
                  <span className={agent.adapter ? "support-state" : "support-state muted"}>
                    {isSelected ? "Collecting" : agent.adapter ? "Supported" : "Coming later"}
                  </span>
                </div>
                <h2>{agentLabel(agent.name)}</h2>
                <p>{agent.version ?? "Version unavailable"}</p>
                <button
                  className="agent-action"
                  disabled={!agent.adapter || selectingAgent !== null}
                  onClick={() => onSelect(agent)}
                  type="button"
                >
                  {isStarting
                    ? "Starting…"
                    : !agent.adapter
                      ? "Not supported yet"
                      : isSelected
                        ? "Continue"
                        : "Start collecting"}
                </button>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty-state agent-empty">
          <div className="empty-icon"><Clock3 size={22} /></div>
          <h3>No agents detected</h3>
          <p>Install a coding agent and restart <code>graphen-trace serve</code> to detect it.</p>
        </div>
      )}
    </section>
  );
}
