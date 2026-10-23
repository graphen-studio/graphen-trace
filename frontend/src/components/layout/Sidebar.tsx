import {
  Activity,
  Boxes,
  ChartNoAxesCombined,
  RadioTower,
} from "lucide-react";

interface SidebarProps {
  activePage: "sessions" | "resources" | null;
  sessionsEnabled: boolean;
  serviceStatus: "connecting" | "connected" | "unavailable";
  onSessions: () => void;
  onResources: () => void;
}

export default function Sidebar({ activePage, sessionsEnabled, serviceStatus, onSessions, onResources }: SidebarProps) {
  const statusLabel = {
    connecting: "Connecting",
    connected: "Connected",
    unavailable: "Unavailable",
  }[serviceStatus];

  return (
    <aside className="sidebar">
      <nav className="sidebar-nav" aria-label="Main navigation">
        <div className="sidebar-section">
          <p className="sidebar-section-label">Observe</p>
          <button
            className={`sidebar-item${activePage === "sessions" ? " active" : ""}`}
            type="button"
            disabled={!sessionsEnabled}
            aria-current={activePage === "sessions" ? "page" : undefined}
            onClick={onSessions}
          >
            <Activity size={17} aria-hidden="true" />
            <span className="sidebar-item-copy">
              <span>Sessions</span>
              <small>Traces and activity</small>
            </span>
          </button>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-section">
          <p className="sidebar-section-label">Agent workspace</p>
          <button
            className={`sidebar-item${activePage === "resources" ? " active" : ""}`}
            type="button"
            aria-current={activePage === "resources" ? "page" : undefined}
            onClick={onResources}
          >
            <Boxes size={17} aria-hidden="true" />
            <span className="sidebar-item-copy">
              <span>Agent resources</span>
              <small>Skills by agent and scope</small>
            </span>
          </button>
          <button className="sidebar-item upcoming" type="button" disabled>
            <RadioTower size={17} aria-hidden="true" />
            <span className="sidebar-item-copy">
              <span>Live proxy</span>
              <small>Real-time tracing</small>
            </span>
            <span className="sidebar-badge">Soon</span>
          </button>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-section">
          <p className="sidebar-section-label">Analyze</p>
          <button className="sidebar-item upcoming" type="button" disabled>
            <ChartNoAxesCombined size={17} aria-hidden="true" />
            <span className="sidebar-item-copy">
              <span>Dashboards</span>
              <small>Usage over time</small>
            </span>
            <span className="sidebar-badge">Soon</span>
          </button>
        </div>
      </nav>

      <div className="sidebar-footer">
        <div className={`sidebar-api-state state-${serviceStatus}`} role="status">
          <span className="sidebar-api-dot" />
          <span>Local API</span>
          <strong>{statusLabel}</strong>
        </div>
        <p>Trace data stays on this machine.</p>
      </div>
    </aside>
  );
}
