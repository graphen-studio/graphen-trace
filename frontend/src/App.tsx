import { Activity, Bot, CircleDollarSign, Clock3, Radio } from "lucide-react";
import { useEffect, useState } from "react";
import AgentPicker from "./components/agents/AgentPicker";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import SessionDetails from "./components/sessions/SessionDetails";
import SessionTable from "./components/sessions/SessionTable";
import { useDashboardData } from "./hooks/useDashboardData";
import { getAgentSelection, startCollection } from "./services/api";
import type { AgentInstallation, CollectionStatus, UsageSummary } from "./types/api";
import { agentLabel } from "./utils/agentLabel";
import { formatCost, formatCount } from "./utils/format";

function selectedSession(): string | null {
  const match = window.location.hash.match(/^#\/sessions\/([^/]+)$/);
  try { return match ? decodeURIComponent(match[1]) : null; }
  catch { return null; }
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

type Theme = "dark" | "light";

function getInitialTheme(): Theme {
  try {
    return localStorage.getItem("graphen-theme") === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function formatMetric(key: string, usage: UsageSummary): string {
  if (key === "sessions") return formatCount(usage.session_count);
  if (key === "cost") return formatCost(usage.reported_cost);
  return formatCount(usage.usage[key]);
}

export default function App() {
  const [collection, setCollection] = useState<CollectionStatus | null>(null);
  const [agents, setAgents] = useState<AgentInstallation[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showAgentPicker, setShowAgentPicker] = useState(true);
  const [selectingAgent, setSelectingAgent] = useState<string | null>(null);
  const [serviceAvailable, setServiceAvailable] = useState<boolean | null>(null);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState(selectedSession);
  const dashboard = useDashboardData(Boolean(selectedAgent) && !showAgentPicker, selectedAgent);
  const sessions = dashboard.data?.sessions ?? [];
  const usage = dashboard.data?.usage ?? null;
  const liveCollection = dashboard.data?.liveCollection ?? null;
  const currentCollection = dashboard.data?.collection ?? collection;

  useEffect(() => {
    const navigate = () => setSessionId(selectedSession());
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute(
      "content",
      theme === "dark" ? "#090a0f" : "#f5f7fb",
    );
    try {
      localStorage.setItem("graphen-theme", theme);
    } catch {
      // The theme still works for this page when browser storage is unavailable.
    }
  }, [theme]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadSelection() {
      try {
        const { agents: installedAgents, collection: status } =
          await getAgentSelection(controller.signal);
        if (!controller.signal.aborted) {
          setCollection(status);
          setAgents(installedAgents);
          setSelectedAgent(status.agent);
          setShowAgentPicker(!status.agent);
          setServiceAvailable(true);
          setError(null);
        }
      } catch {
        if (!controller.signal.aborted) {
          setServiceAvailable(false);
          setError("Local service unavailable.");
        }
      }
    }
    void loadSelection();
    return () => controller.abort();
  }, []);

  async function selectAgent(agent: AgentInstallation) {
    if (!agent.adapter || selectingAgent) return;
    setSelectingAgent(agent.name);
    setError(null);
    try {
      const result = await startCollection(agent.name);
      setCollection(result);
      setSelectedAgent(result.agent);
      setShowAgentPicker(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not start collection.");
    } finally {
      setSelectingAgent(null);
    }
  }

  function openSessions() {
    setShowAgentPicker(false);
    setSessionId(null);
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }

  function toggleTheme() {
    setTheme((current) => current === "dark" ? "light" : "dark");
  }

  const serviceStatus = dashboard.error
    ? "unavailable"
    : serviceAvailable === null
      ? "connecting"
      : serviceAvailable
        ? "connected"
        : "unavailable";

  return (
    <main className="shell">
      <TopBar
        theme={theme}
        selectedAgent={selectedAgent}
        collectionState={currentCollection?.state}
        onChangeAgent={() => setShowAgentPicker(true)}
        onToggleTheme={toggleTheme}
      />

      <div className="app-layout">
        <Sidebar
          active={!showAgentPicker}
          sessionsEnabled={Boolean(selectedAgent)}
          serviceStatus={serviceStatus}
          onSessions={openSessions}
        />
        <div className="main-content">
          {showAgentPicker ? (
            <AgentPicker
              agents={agents}
              error={error}
              selectingAgent={selectingAgent}
              selectedAgent={selectedAgent}
              onSelect={(agent) => void selectAgent(agent)}
            />
          ) : (
            <>
              <section className="intro">
                <div>
                  <div className="eyebrow"><Activity size={14} /> AGENT OBSERVABILITY</div>
                  <h1>Trace your work.</h1>
                  <p>
                    See what {selectedAgent ? agentLabel(selectedAgent) : "your coding agent"} is doing, as it happens.
                  </p>
                </div>
              </section>

              <section className="metrics">
                {metrics.map(({ label, key, icon: Icon, color }) => (
                  <article className="metric" key={label}>
                    <div className={`metric-icon ${color}`}><Icon size={18} /></div>
                    <div>
                      <div className="metric-value">{usage ? formatMetric(key, usage) : "—"}</div>
                      <div className="metric-label">
                        {label}
                        {usage &&
                          (key === "cost"
                            ? usage.cost_incomplete
                            : usage.usage_incomplete.includes(key)) && " (partial)"}
                      </div>
                    </div>
                  </article>
                ))}
              </section>

              <p className="collection-state">
                Native token categories across all synchronized sessions; cache and reasoning are shown separately, without assuming provider totals. Cost currency/calculation are unverified, not confirmed billing.
              </p>
              {((currentCollection?.warnings?.length ?? 0) > 0 || currentCollection?.state === "unavailable") && (
                <aside className="collection-state" role="status">
                  <strong>Collection warning — captured data remains available</strong>
                  {currentCollection?.state === "unavailable" && <p>{currentCollection.detail}</p>}
                  <ul>{currentCollection?.warnings?.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                </aside>
              )}
              {(liveCollection?.state === "partial" || liveCollection?.state === "unavailable") && (
                <aside className="collection-state" role="status">
                  <strong>Live events: {liveCollection.state}</strong>
                  <p>{liveCollection.detail}</p>
                  <ul>{liveCollection.warnings?.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                </aside>
              )}

              {sessionId ? (
                <>
                  <SessionDetails key={sessionId} sessionId={sessionId} />
                  <p className="collection-state" role="status">
                    {error || dashboard.error || (currentCollection
                      ? `${currentCollection.state}: ${currentCollection.detail}`
                      : "Connecting…")}
                  </p>
                </>
              ) : dashboard.data ? (
                <SessionTable sessions={sessions} />
              ) : (
                <section className="sessions panel empty-state">
                  <div className="empty-icon"><Clock3 size={22} /></div>
                  <h3>Loading sessions</h3>
                  <p>{dashboard.error || "Connecting to the local service…"}</p>
                </section>
              )}
              <footer>Local-first observability <span>·</span> Your data stays on this machine</footer>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
