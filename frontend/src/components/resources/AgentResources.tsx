import { useEffect, useMemo, useState } from "react";
import { BookOpen, FileText, Folder, Globe2 } from "lucide-react";
import type { AgentSkill } from "../../types/api";
import { getAgentResources } from "../../services/api";
import { MarkdownContent } from "../sessions/SessionTimeline";

export default function AgentResources() {
  const [items, setItems] = useState<AgentSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAgentResources(controller.signal)
      .then(({ items: resources }) => setItems(resources))
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : "Could not load resources.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  return <AgentResourcesContent items={items} loading={loading} error={error} />;
}

export function AgentResourcesContent({
  items,
  loading,
  error,
}: {
  items: AgentSkill[];
  loading: boolean;
  error: string | null;
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = useMemo(() => {
    const key = selectedKey ?? resourceKey(items[0]);
    return items.find((item) => resourceKey(item) === key) ?? items[0] ?? null;
  }, [items, selectedKey]);
  const selectedDocument = useMemo(
    () => selected ? splitSkillDocument(selected.content) : null,
    [selected],
  );

  return (
    <section className="resource-explorer">
      <header className="resource-header">
        <div className="eyebrow"><BookOpen size={14} aria-hidden="true" /> AGENT WORKSPACE</div>
        <h1>Agent resources</h1>
        <p>Skills discovered from project and global locations for supported agents.</p>
      </header>
      {error && <p className="resource-message" role="alert">{error}</p>}
      {loading ? (
        <section className="panel empty-state"><p>Discovering local skills…</p></section>
      ) : items.length === 0 ? (
        <section className="panel empty-state">
          <div className="empty-icon"><FileText size={22} aria-hidden="true" /></div>
          <h3>No skills found</h3>
          <p>Add a <code>SKILL.md</code> to a supported project or global skills directory.</p>
        </section>
      ) : (
        <div className="resource-workspace">
          <section className="panel resource-list" aria-label="Discovered skills">
            <div className="resource-list-heading">
              <h2>Skills</h2><span>{items.length}</span>
            </div>
            {items.map((item) => {
              const key = resourceKey(item);
              const active = selected != null && resourceKey(selected) === key;
              const ScopeIcon = item.scope === "project" ? Folder : Globe2;
              return (
                <button
                  className={`resource-item${active ? " active" : ""}`}
                  type="button"
                  key={key}
                  aria-pressed={active}
                  onClick={() => setSelectedKey(key)}
                >
                  <span className="resource-item-icon"><FileText size={15} aria-hidden="true" /></span>
                  <span className="resource-item-copy">
                    <strong>{item.name}</strong>
                    <span className="resource-item-meta">
                      <span className="resource-scope-label">
                        <ScopeIcon size={11} aria-hidden="true" />
                        {item.scope === "global" ? "Global" : "Project"}
                      </span>
                      <span className="resource-support-label">
                        {item.agents.map((agent) => agent.name).join(" · ")}
                      </span>
                    </span>
                  </span>
                </button>
              );
            })}
          </section>
          {selected && (
            <article className="panel resource-detail">
              <header className="resource-detail-heading">
                <div>
                  <div className="resource-badges">
                    <span className={`resource-scope-badge scope-${selected.scope}`}>
                      {selected.scope === "project"
                        ? <Folder size={13} aria-hidden="true" />
                        : <Globe2 size={13} aria-hidden="true" />}
                      {selected.scope === "global" ? "Global skill" : "Project skill"}
                    </span>
                    {selected.agents.map((agent) => (
                      <span className="resource-agent-badge prominent" key={agent.id}>
                        <span className="resource-agent-dot" aria-hidden="true" />
                        {agent.name} supported
                      </span>
                    ))}
                  </div>
                  <h2>{selected.name}</h2>
                  {!selectedDocument?.metadata.some(({ key }) => key === "description") && selected.description && (
                    <p>{selected.description}</p>
                  )}
                </div>
              </header>
              <div className="resource-file-path">{selected.path}</div>
              {selectedDocument && selectedDocument.metadata.length > 0 && (
                <section className="resource-frontmatter" aria-label="Skill front matter metadata">
                  <div className="resource-frontmatter-heading">
                    <div>
                      <span className="resource-frontmatter-label">SKILL DEFINITION</span>
                      <h3>Front matter</h3>
                    </div>
                    <span className="resource-frontmatter-format">YAML metadata</span>
                  </div>
                  <dl className="resource-metadata-grid">
                    {selectedDocument.metadata.map(({ key, value }) => (
                      <div className={`resource-metadata-field${key === "description" ? " is-description" : ""}`} key={key}>
                        <dt>{key}</dt>
                        <dd>{value || <span className="resource-metadata-empty">Not specified</span>}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
              <div className="resource-content">
                <div className="resource-content-heading">
                  <span className="resource-frontmatter-label">INSTRUCTIONS</span>
                  <h3>Skill content</h3>
                </div>
                <MarkdownContent source={selectedDocument?.markdown ?? selected.content} />
              </div>
            </article>
          )}
        </div>
      )}
    </section>
  );
}

function resourceKey(item: AgentSkill | undefined): string {
  return item?.path ?? "";
}

function splitSkillDocument(content: string): {
  metadata: { key: string; value: string }[];
  markdown: string;
} {
  const match = content.match(/^\uFEFF?---\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)/);
  if (!match) return { metadata: [], markdown: content };

  const metadata: { key: string; value: string }[] = [];
  for (const line of match[1].split(/\r?\n/)) {
    const field = line.match(/^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$/);
    if (field) {
      metadata.push({ key: field[1], value: field[2] ?? "" });
    } else if (metadata.length > 0) {
      const previous = metadata[metadata.length - 1];
      previous.value += `${previous.value ? "\n" : ""}${line}`;
    }
  }
  return { metadata, markdown: content.slice(match[0].length) };
}
