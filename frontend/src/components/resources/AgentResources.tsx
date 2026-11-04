import { useEffect, useMemo, useState } from 'react';
import { BookOpen, FileText, Folder, Globe2 } from 'lucide-react';
import type { AgentResource } from '../../types/api';
import { getAgentResources } from '../../services/api';
import { MarkdownContent } from '../sessions/SessionTimeline';

export default function AgentResources() {
  const [items, setItems] = useState<AgentResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAgentResources(controller.signal)
      .then(({ items: resources }) => setItems(resources))
      .catch((failure: unknown) => {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : 'Could not load resources.');
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
  items: AgentResource[];
  loading: boolean;
  error: string | null;
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = useMemo(() => {
    const key = selectedKey ?? resourceKey(items[0]);
    return items.find((item) => resourceKey(item) === key) ?? items[0] ?? null;
  }, [items, selectedKey]);
  const selectedDocument = useMemo(
    () => (selected ? splitResourceDocument(selected.content) : null),
    [selected],
  );
  const selectedInclusion = selected
    ? steeringInclusion(selected, selectedDocument?.metadata ?? [])
    : null;
  const selectedKindLabel = selected?.kind === 'skill' ? 'skill' : 'steering';
  const selectedScopeLabel = selected?.scope === 'global' ? 'Global' : 'Project';

  return (
    <section className="resource-explorer">
      <header className="resource-header">
        <div className="eyebrow">
          <BookOpen size={14} aria-hidden="true" /> AGENT WORKSPACE
        </div>
        <h1>Agent resources</h1>
        <p>Skills and steering documents from supported project and global locations.</p>
      </header>
      {error && (
        <p className="resource-message" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <section className="panel empty-state">
          <p>Discovering local resources…</p>
        </section>
      ) : items.length === 0 ? (
        <section className="panel empty-state">
          <div className="empty-icon">
            <FileText size={22} aria-hidden="true" />
          </div>
          <h3>No agent resources found</h3>
          <p>
            Add a <code>SKILL.md</code>, steering document, or <code>AGENTS.md</code> to a supported
            location.
          </p>
        </section>
      ) : (
        <div className="resource-workspace">
          <section className="panel resource-list" aria-label="Discovered agent resources">
            <div className="resource-list-heading">
              <h2>Resources</h2>
              <span>{items.length}</span>
            </div>
            {items.map((item) => {
              const key = resourceKey(item);
              const active = selected != null && resourceKey(selected) === key;
              const ScopeIcon = item.scope === 'project' ? Folder : Globe2;
              const inclusion = steeringInclusion(
                item,
                item.kind === 'steering' ? splitResourceDocument(item.content).metadata : [],
              );
              return (
                <button
                  className={`resource-item${active ? ' active' : ''}`}
                  type="button"
                  key={key}
                  aria-pressed={active}
                  onClick={() => setSelectedKey(key)}
                >
                  <span className="resource-item-icon">
                    <FileText size={15} aria-hidden="true" />
                  </span>
                  <span className="resource-item-copy">
                    <strong>{item.name}</strong>
                    <span className="resource-item-meta">
                      <span className="resource-scope-label">
                        <ScopeIcon size={11} aria-hidden="true" />
                        {item.scope === 'global' ? 'Global' : 'Project'}
                      </span>
                      <span className="resource-scope-label">
                        {item.kind === 'skill' ? 'Skill' : 'Steering'}
                      </span>
                      {inclusion && (
                        <span className="resource-inclusion-list-label">{inclusion.label}</span>
                      )}
                      <span className="resource-support-label">
                        {item.agents.map((agent) => agent.name).join(' · ')}
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
                      {selected.scope === 'project' ? (
                        <Folder size={13} aria-hidden="true" />
                      ) : (
                        <Globe2 size={13} aria-hidden="true" />
                      )}
                      {selectedScopeLabel} {selectedKindLabel}
                    </span>
                    <span className="resource-kind-badge">
                      {selected.kind === 'skill' ? 'Agent Skill' : 'Kiro Steering'}
                    </span>
                    {selected.agents.map((agent) => (
                      <span className="resource-agent-badge prominent" key={agent.id}>
                        <span className="resource-agent-dot" aria-hidden="true" />
                        {agent.name} supported
                      </span>
                    ))}
                  </div>
                  <h2>{selected.name}</h2>
                  {!selectedDocument?.metadata.some(({ key }) => key === 'description') &&
                    selected.description && <p>{selected.description}</p>}
                </div>
              </header>
              <div className="resource-file-path">{selected.path}</div>
              {selectedInclusion && (
                <section
                  className="resource-inclusion-summary"
                  aria-label="Configured steering inclusion"
                >
                  <div className="resource-inclusion-summary-heading">
                    <span className="resource-frontmatter-label">CONFIGURED INCLUSION</span>
                    <strong>{selectedInclusion.label}</strong>
                  </div>
                  {selectedInclusion.fileMatchPattern !== undefined && (
                    <div className="resource-inclusion-pattern">
                      <span>File match pattern</span>
                      <code>{selectedInclusion.fileMatchPattern || 'Not specified'}</code>
                    </div>
                  )}
                  <p>{selectedInclusion.note}</p>
                  <p className="resource-inclusion-caveat">
                    This shows the file's configured rule; Graphen cannot verify whether Kiro loaded
                    it in a particular session. Behavior may vary by Kiro engine and version.
                  </p>
                </section>
              )}
              {selectedDocument && selectedDocument.metadata.length > 0 && (
                <section
                  className="resource-frontmatter"
                  aria-label="Resource front matter metadata"
                >
                  <div className="resource-frontmatter-heading">
                    <div>
                      <span className="resource-frontmatter-label">
                        {selected.kind === 'skill' ? 'SKILL DEFINITION' : 'STEERING DOCUMENT'}
                      </span>
                      <h3>Front matter</h3>
                    </div>
                    <span className="resource-frontmatter-format">YAML metadata</span>
                  </div>
                  <dl className="resource-metadata-grid">
                    {selectedDocument.metadata.map(({ key, value }) => (
                      <div
                        className={`resource-metadata-field${key === 'description' ? ' is-description' : ''}`}
                        key={key}
                      >
                        <dt>{key}</dt>
                        <dd>
                          {value || <span className="resource-metadata-empty">Not specified</span>}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>
              )}
              <div className="resource-content">
                <div className="resource-content-heading">
                  <span className="resource-frontmatter-label">INSTRUCTIONS</span>
                  <h3>{selected.kind === 'skill' ? 'Skill content' : 'Steering instructions'}</h3>
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

function resourceKey(item: AgentResource | undefined): string {
  return item?.path ?? '';
}

interface ResourceDocument {
  metadata: { key: string; value: string }[];
  markdown: string;
}

interface SteeringInclusion {
  label: string;
  note: string;
  fileMatchPattern?: string;
}

function steeringInclusion(
  resource: AgentResource,
  metadata: ResourceDocument['metadata'],
): SteeringInclusion | null {
  if (resource.kind !== 'steering') return null;

  const fileName = resource.path.split(/[\\/]/).pop()?.toLowerCase();
  if (fileName === 'agents.md') {
    return {
      label: 'Always included',
      note: 'AGENTS.md is always included by Kiro and does not use steering inclusion modes.',
    };
  }

  const inclusionField = metadata.find(({ key }) => key === 'inclusion');
  if (!inclusionField) {
    return {
      label: 'Always included (default)',
      note: 'No inclusion mode is declared; Kiro documents always as the default.',
    };
  }

  const mode = yamlScalar(inclusionField.value).toLowerCase();
  switch (mode) {
    case 'always':
      return {
        label: 'Always included',
        note: "Declared by the steering file's front matter.",
      };
    case 'auto':
      return {
        label: 'Auto',
        note: 'Configured for context-based inclusion when Kiro considers the content relevant.',
      };
    case 'manual':
      return {
        label: 'Manual',
        note: 'Configured for explicit, manual inclusion.',
      };
    case 'filematch': {
      const pattern = metadata.find(({ key }) => key === 'fileMatchPattern');
      return {
        label: 'File match',
        note: 'Configured to match active files using this pattern.',
        fileMatchPattern: pattern ? yamlScalar(pattern.value) : '',
      };
    }
    default:
      return {
        label: 'Unrecognized inclusion mode',
        note: `The steering file declares an inclusion mode Graphen does not recognize: ${inclusionField.value}.`,
      };
  }
}

function yamlScalar(value: string): string {
  const trimmed = value.trim();
  if (
    trimmed.length >= 2 &&
    ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'")))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function splitResourceDocument(content: string): {
  metadata: { key: string; value: string }[];
  markdown: string;
} {
  const match = content.match(/^\uFEFF?---\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)/);
  if (!match) return { metadata: [], markdown: content };

  const metadata: { key: string; value: string }[] = [];
  for (const line of match[1].split(/\r?\n/)) {
    const field = line.match(/^([A-Za-z0-9_-]+):(?:[ \t]*(.*))?$/);
    if (field) {
      metadata.push({ key: field[1], value: field[2] ?? '' });
    } else if (metadata.length > 0) {
      const previous = metadata[metadata.length - 1];
      previous.value += `${previous.value ? '\n' : ''}${line}`;
    }
  }
  return { metadata, markdown: content.slice(match[0].length) };
}
