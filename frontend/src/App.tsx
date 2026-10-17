import { Activity, Bot, Boxes, CircleDollarSign, Clock3, Radio, Search } from "lucide-react";

const metrics = [
  { label: "Input tokens", value: "—", icon: Activity, color: "blue" },
  { label: "Output tokens", value: "—", icon: Radio, color: "cyan" },
  { label: "Active sessions", value: "0", icon: Bot, color: "green" },
  { label: "Known cost", value: "—", icon: CircleDollarSign, color: "purple" },
];

export default function App() {
  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <img src="/logo-without-text.png" alt="" />
          <span>Graphen <b>Trace</b></span>
        </div>
        <div className="connection"><span /> Local service</div>
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
        {metrics.map(({ label, value, icon: Icon, color }) => (
          <article className="metric" key={label}>
            <div className={`metric-icon ${color}`}><Icon size={18} /></div>
            <div><div className="metric-value">{value}</div><div className="metric-label">{label}</div></div>
          </article>
        ))}
      </section>

      <section className="sessions panel">
        <div className="section-heading">
          <div><h2>Sessions</h2><p>Your agent activity will appear here</p></div>
          <button className="filter"><Search size={15} /> Search sessions</button>
        </div>
        <div className="empty-state">
          <div className="empty-icon"><Clock3 size={22} /></div>
          <h3>Waiting for agent activity</h3>
          <p>Start OpenCode or run <code>graphen-trace discover</code> to check your setup.</p>
          <div className="status-chip"><span /> Collector ready · OpenCode adapter foundation</div>
        </div>
      </section>
      <footer>Local-first observability <span>·</span> Your data stays on this machine</footer>
    </main>
  );
}
