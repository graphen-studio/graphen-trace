import { Check, ChevronRight, Copy } from "lucide-react";
import { useId, useMemo, useState } from "react";

// Match complete JSON strings before literals so values inside quotes stay intact.
const jsonToken = /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g;

function tokenClass(token: string): string {
  if (token.startsWith('"')) return token.endsWith(":") ? "json-key" : "json-string";
  if (token === "null") return "json-null";
  if (token === "true" || token === "false") return "json-boolean";
  return "json-number";
}

export function Payload({ label, value }: { label: string; value: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const contentId = useId();
  const payload = useMemo(() => {
    if (value == null) return null;
    if (typeof value !== "string") {
      return { text: JSON.stringify(value, null, 2), json: true };
    }
    // Keep source strings verbatim; parsing could round large numeric IDs.
    return { text: value, json: false };
  }, [value]);

  if (!payload) return null;
  const text = payload.text ?? String(value);

  async function copyPayload() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <section className="source-payload">
      <div className="payload-header">
        <button
          className="payload-toggle"
          type="button"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setExpanded((current) => !current)}
        >
          <ChevronRight className={expanded ? "payload-chevron expanded" : "payload-chevron"} size={14} aria-hidden="true" />
          <span>{label}</span>
          {payload.json && <span className="payload-format">JSON</span>}
        </button>
        <button
          className="payload-copy"
          type="button"
          onClick={() => void copyPayload()}
          aria-label={copyState === "copied" ? `${label} copied` : copyState === "failed" ? `Could not copy ${label}` : `Copy ${payload.json ? "JSON" : "text"}: ${label}`}
          title={copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : `Copy ${payload.json ? "JSON" : "text"}`}
        >
          {copyState === "copied" ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
          <span>{copyState === "copied" ? "Copied" : copyState === "failed" ? "Failed" : "Copy"}</span>
        </button>
      </div>
      <div className="payload-content" id={contentId} hidden={!expanded}>
        <pre className={payload.json ? "json-payload" : undefined}>
          <code>{payload.json
            ? text.split(jsonToken).map((token, index) => index % 2
              ? <span className={tokenClass(token)} key={index}>{token}</span>
              : token)
            : text}</code>
        </pre>
      </div>
    </section>
  );
}
