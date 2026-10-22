export function HighlightedText({ text, query }: { text: string; query: string }) {
  const term = query.trim();
  if (!term) return <>{text}</>;
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return <>{text.split(new RegExp(`(${escaped})`, "gi")).map((part, index) =>
    index % 2 ? <mark className="session-search-highlight" key={index}>{part}</mark> : part,
  )}</>;
}
