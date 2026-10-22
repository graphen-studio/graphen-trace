import { useMemo } from "react";

// Match complete JSON strings before literals so values inside quotes stay intact.
const jsonToken = /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g;

function tokenClass(token: string): string {
  if (token.startsWith('"')) return token.endsWith(":") ? "json-key" : "json-string";
  if (token === "null") return "json-null";
  if (token === "true" || token === "false") return "json-boolean";
  return "json-number";
}

export function Payload({ label, value }: { label: string; value: unknown }) {
  const payload = useMemo(() => {
    if (value == null) return null;
    if (typeof value !== "string") {
      return { text: JSON.stringify(value, null, 2), json: true };
    }
    // Keep string payloads verbatim: parsing them could round large numeric IDs.
    // Structured JSON supplied by the API is formatted and highlighted above.
    return { text: value, json: false };
  }, [value]);

  if (!payload) return null;
  return (
    <details className="source-payload">
      <summary>{label}{payload.json && <span className="payload-format">JSON</span>}</summary>
      <pre className={payload.json ? "json-payload" : undefined}>
        <code>{payload.json
          ? payload.text.split(jsonToken).map((token, index) => index % 2
            ? <span className={tokenClass(token)} key={index}>{token}</span>
            : token)
          : payload.text}</code>
      </pre>
    </details>
  );
}
