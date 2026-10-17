# Graphen Trace

Tracing and observability for coding agents. This initial implementation collects
complete OpenCode session/message records and native token counters into a local Graphen SQLite
database. The dashboard reads only the Graphen API.

## Development

```sh
make install
make frontend-install
make frontend-build
make cli ARGS="serve"
```

Open `http://127.0.0.1:8765/`. For UI development, run `make frontend-dev` in a
separate terminal; Vite forwards `/api` to the local backend.

## Passive OpenCode collection

- Currently validated: **OpenCode 2.0.32**, SQLite V2 dialect (`session_v2` and
  `session_message`). Other versions, including V1, are explicitly rejected for
  collection rather than interpreted using an incompatible reader.
- `discover` only detects installations. `serve` and `run opencode` start the
  collector in the FastAPI lifespan and stop it on shutdown.
- The source is opened with `mode=ro` and `query_only`, using consistent read
  transactions that include WAL changes. No agent configuration is modified.
- Each cycle checks session/message metadata watermarks. Only changed sessions
  have their message JSON read again. Replacements, revisions, and source
  deletions are committed together in the Graphen database. This is projection
  polling, not an event-log cursor: V2 event-log compatibility is not established.
- Captured: session IDs, titles, directory, parent ID, source version, latest
  observed model, message count, timestamps, native usage categories, and timeline
  metadata. Each tool execution retains its native call ID, name, status, times,
  duration, exit code and child session ID when provided by the source. Complete
  native records are also retained, including prompts, responses, exposed
  reasoning, tool arguments/results, errors, provider metadata and attachment
  references. Native records can be expanded in the session timeline.
- The timeline links generations to the latest preceding user message by native
  sequence. This association is labeled as inferred, not a native parent ID.
  Repeated tool call IDs are shown once, using their latest observed state.
- No automatic redaction, truncation or expiry is applied. This database contains
  sensitive content and may include secrets printed during execution. No
  provider credentials or credential headers are captured. The local OpenCode
  service password is used only in memory to authenticate its event stream.
  Attachment references do not cause external files or URLs to be fetched. The
  available-tool catalog remains unavailable from this SQLite reader.
- Agent-reported cost is preserved and displayed as a native value: currency and
  calculation are unverified, not confirmed billing.
- Missing usage remains `null`. Native token categories are not combined into a
  provider total, and session aggregate counters are not added to message usage.
  Totals with missing generation counters are labeled partial. The global
  dashboard aggregates all synchronized sessions, independently of list pagination.

Default paths respect `XDG_DATA_HOME` (fallback `~/.local/share`):

| Variable | Default |
| --- | --- |
| `GRAPHEN_TRACE_DATABASE` | `$XDG_DATA_HOME/graphen-trace/trace.db` |
| `GRAPHEN_TRACE_OPENCODE_DATABASE` | `$XDG_DATA_HOME/opencode/opencode.db` |
| `GRAPHEN_TRACE_OPENCODE_SERVICE_FILE` | `$XDG_STATE_HOME/opencode/service.json` |
| `GRAPHEN_TRACE_OPENCODE_URL` | Discover the existing shared service |
| `GRAPHEN_TRACE_OPENCODE_PASSWORD` | Use local service registration authentication |

`GET /api/sessions?limit=50&offset=0` returns observed sessions.
`GET /api/sessions/{id}` returns one session; missing sessions return HTTP 404.
`GET /api/sessions/{id}/timeline?limit=50&offset=0` returns a page of ordered
timeline records and its total count. Click a session title in the dashboard to
open its details, navigate timeline pages, or follow parent/child session links.
`GET /api/collection` reports collection state, coverage, and last successful sync.
`GET /api/usage` returns observed native token/cost aggregates and completeness.
`GET /api/events?session_id=...&limit=50&offset=0` returns persisted live events.
`GET /api/collection/live` returns SSE health and recent connection boundaries.
Unavailable sources do not stop the dashboard. Historical records remain available
and the collection status indicates that they may be stale.

## Checks and distribution

```sh
make lint
make test
make build
```

Install frontend dependencies explicitly before building. The build includes
`graphen_trace/web/dist` in the wheel and sdist; installed users do not need Node.

Graphen schema version 2 adds timeline storage alongside session summaries. The
existing database upgrades automatically; the normalization revision forces a
one-time refresh of sessions to populate their timeline. The full-content revision
also reimports sessions previously captured as metadata only. No source data is edited.

Graphen schema version 3 adds independently stored live events, observed native
watermarks, and connection history. SSE connects only to an existing loopback
OpenCode 2.0.32 service, validating content types and using authentication only
in memory. No OpenCode service is started, stopped or reconfigured. Native IDs
deduplicate re-observed events. Events do not add a second copy of message usage
to dashboard totals. SQLite polling keeps running even if SSE is unavailable.

The SSE contract is volatile: connection/reconnection does not replay missed
events. `possible_gap` remains true to avoid claiming complete historical capture.
Only the connected instance is observed; separate standalone instances are not.
Connection transitions survive Graphen restarts. No UI redesign is included in
this stage; the new events are exposed through the API for the future interface.

Next steps: validated V1 dialect, provider request/response capture through the
optional proxy, available-tool catalog validation, and event-based synchronization
when its contract is confirmed. The current
revision index scans metadata each cycle; optimize it as
history grows rather than assuming a V1 event stream exists in V2.
