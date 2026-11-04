import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { AgentResource } from '../../types/api';
import { AgentResourcesContent } from './AgentResources';

const resources: AgentResource[] = [
  {
    kind: 'skill',
    scope: 'project',
    name: 'shared',
    description: 'Review changes carefully',
    path: '/workspace/.agents/skills/shared/SKILL.md',
    content:
      '---\nname: shared\ndescription: Review changes carefully\nlicense: MIT\nmetadata:\n  audience: developers\n---\n# Review safely\n\n- Check the diff\n',
    agents: [
      { id: 'opencode', name: 'OpenCode' },
      { id: 'pi', name: 'Pi' },
    ],
  },
  {
    kind: 'skill',
    scope: 'global',
    name: 'docs',
    description: 'Write documentation',
    path: '/home/user/.pi/agent/skills/docs/SKILL.md',
    content: '# Docs',
    agents: [{ id: 'pi', name: 'Pi' }],
  },
  {
    kind: 'steering',
    scope: 'project',
    name: 'api-standards.md',
    description: 'Follow the API conventions',
    path: '/workspace/.kiro/steering/api-standards.md',
    content:
      '---\ninclusion: auto\ndescription: Follow the API conventions\n---\n# API standards\n\nUse the current API version.\n',
    agents: [{ id: 'kiro', name: 'Kiro' }],
  },
  {
    kind: 'steering',
    scope: 'project',
    name: 'typescript.md',
    description: '',
    path: '/workspace/.kiro/steering/typescript.md',
    content:
      '---\ninclusion: fileMatch\nfileMatchPattern: ["src/**/*.ts", "src/**/*.tsx"]\n---\n# TypeScript\n',
    agents: [{ id: 'kiro', name: 'Kiro' }],
  },
  {
    kind: 'steering',
    scope: 'project',
    name: 'default.md',
    description: '',
    path: '/workspace/.kiro/steering/default.md',
    content: '# Default steering\n',
    agents: [{ id: 'kiro', name: 'Kiro' }],
  },
  {
    kind: 'steering',
    scope: 'project',
    name: 'AGENTS.md',
    description: '',
    path: '/workspace/AGENTS.md',
    content: '---\ninclusion: manual\n---\n# Agent instructions\n',
    agents: [{ id: 'kiro', name: 'Kiro' }],
  },
];

describe('agent resources', () => {
  it('renders discovered providers, scope, and Markdown content', () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={resources} loading={false} error={null} />,
    );

    expect(html).toContain('OpenCode');
    expect(html).toContain('Project');
    expect(html).toContain('Pi');
    expect(html).toContain('global');
    expect(html).toContain('OpenCode supported');
    expect(html).toContain('Pi supported');
    expect(html).toContain('Kiro');
    expect(html).toContain('Project skill');
    expect(html).toContain('Front matter');
    expect(html).toContain('YAML metadata');
    expect(html).toContain('<dt>license</dt>');
    expect(html).toContain('audience: developers');
    expect(html).toContain('<h1>Review safely</h1>');
    expect(html).toContain('Check the diff');
    expect(html).toContain('/workspace/.agents/skills/shared/SKILL.md');
    expect(html).not.toContain('<hr');
    expect(html.match(/<strong>shared<\/strong>/g)).toHaveLength(1);
  });

  it('renders Kiro steering metadata and instructions distinctly from skills', () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={[resources[2]]} loading={false} error={null} />,
    );

    expect(html).toContain('Kiro Steering');
    expect(html).toContain('Project steering');
    expect(html).toContain('STEERING DOCUMENT');
    expect(html).toContain('Steering instructions');
    expect(html).toContain('<dt>inclusion</dt>');
    expect(html).toContain('Use the current API version.');
    expect(html).toContain('api-standards.md');
    expect(html).toContain('Auto');
    expect(html).toContain('Graphen cannot verify whether Kiro loaded it');
  });

  it('shows fileMatch patterns for steering documents', () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={[resources[3]]} loading={false} error={null} />,
    );

    expect(html).toContain('File match');
    expect(html).toContain('File match pattern');
    expect(html).toContain('src/**/*.ts');
    expect(html).toContain('src/**/*.tsx');
  });

  it('does not invent a fileMatch pattern or mislabel manual inclusion', () => {
    const missingPattern = {
      ...resources[3],
      content: '---\ninclusion: fileMatch\n---\n# No pattern\n',
    };
    const manual = {
      ...resources[2],
      content: '---\ninclusion: manual\n---\n# Manual steering\n',
    };
    const missingPatternHtml = renderToStaticMarkup(
      <AgentResourcesContent items={[missingPattern]} loading={false} error={null} />,
    );
    const manualHtml = renderToStaticMarkup(
      <AgentResourcesContent items={[manual]} loading={false} error={null} />,
    );

    expect(missingPatternHtml).toContain('Not specified');
    expect(manualHtml).toContain('Manual');
    expect(manualHtml).not.toContain('Always included');
  });

  it('shows default and AGENTS.md inclusion rules accurately', () => {
    const defaultHtml = renderToStaticMarkup(
      <AgentResourcesContent items={[resources[4]]} loading={false} error={null} />,
    );
    const agentsHtml = renderToStaticMarkup(
      <AgentResourcesContent items={[resources[5]]} loading={false} error={null} />,
    );

    expect(defaultHtml).toContain('Always included (default)');
    expect(agentsHtml).toContain('Always included');
    expect(agentsHtml).toContain('AGENTS.md is always included by Kiro');
  });

  it('emphasizes global origin and provider support in the selected skill', () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={[resources[1]]} loading={false} error={null} />,
    );

    expect(html).toContain('Global skill');
    expect(html).toContain('Pi supported');
  });

  it('renders a helpful empty state', () => {
    const html = renderToStaticMarkup(
      <AgentResourcesContent items={[]} loading={false} error={null} />,
    );

    expect(html).toContain('No agent resources found');
    expect(html).toContain('SKILL.md');
    expect(html).toContain('AGENTS.md');
  });
});
