const agentNames: Record<string, string> = {
  opencode: "OpenCode",
  claude: "Claude Code",
  codex: "Codex",
  kiro: "Kiro",
  pi: "Pi.dev",
};

export function agentLabel(name: string): string {
  return agentNames[name] ?? name;
}
