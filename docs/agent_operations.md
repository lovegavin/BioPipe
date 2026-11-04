# Operating BioPipe with an agent

BioPipe exposes one engine through MCP, CLI and HTTP. These operating guides are
for **using** the software; SDK/protocol documentation is for writing extensions.
No model, desktop window or source checkout is required to retrieve a guide.

## Three layers

| Layer | MCP | CLI | Contents |
| --- | --- | --- | --- |
| Entry | Server initialization instructions; `biopipe_guide()` | `biopipe help` | Short rules, permissions, task routing |
| Task | `biopipe_guide(topic="workflow")` | `biopipe help workflow` | One executable scenario at a time |
| Operator | `biopipe_operator_search`, then `biopipe_operator_describe` | `biopipe operators search`, then `describe` | Installed schemas/contracts and selected Markdown |

`biopipe help index` lists topics: start, operators, canvas, workflow, jobs,
results and api. `guide` is an alias of `help`. Guides are package resources under
`biopipe/guides/`, included in wheels. MCP also exposes `biopipe://guide` and
`biopipe://guide/{topic}`. Clients that do not display server instructions or
resources can call the guide tool explicitly. A client controls what reaches its
model; BioPipe cannot force it to inject or obey instructions.

The same English text is available through authenticated GET `/api/v1/guides`
and `/api/v1/guides/{topic}`. Responses include software version and a content
SHA-256. Send `if_sha256` to suppress unchanged text. Unknown topics fail explicitly;
there is no arbitrary-file reading endpoint. Reading CLI help starts no service.

## Small responses by default

- MCP/CLI search defaults to five brief, relevance-ranked matches. Exact IDs rank
  first. Word boundaries avoid matches such as liability/reliability. Declared
  multilingual aliases work; this is lexical search, not automatic translation.
- Search summaries omit implementation hashes and repeated descriptions. Long
  summaries are explicitly marked as truncated. `next_offset` supports paging.
- Describe `view=schema` returns execution schemas/contracts and a section index;
  `view=docs` retrieves only the requested documentation plus identity. `view=full`
  restores complete descriptor metadata. `sections=['*']` explicitly reads all MD.
- MCP job status and CLI `jobs get` default to brief. Use `view=full` / `--view full`
  for runtime internals. `biopipe_job(wait_seconds=30)` waits inside the tool;
  CLI `jobs wait <id> --timeout 30 --brief` does the same. Timeout never cancels.
- Logs default to 4 KiB of text. Choose base64 for exact byte reconstruction or
  both for compatibility. Offsets remain bytes, with the same reset/done semantics.
- `--compact` removes JSON indentation. `run --brief` omits large job details.
- `workflow prepare ... --require-files --output prepared.json` freezes, validates
  and writes the graph. Use that prepared graph for execution; do not run a second
  identical validation just to follow a checklist.

HTTP search/describe/job/log defaults retain their prior full representations;
new views are explicit query/body options. CLI `operators list` and MCP catalog
remain compatibility operations. Operator v3, saved parameter files, transaction
revisions, run permissions, streaming/spill and SSH scheduling are unchanged.
After upgrading, restart an idle old service/desktop so adapters reach the updated
API; do not stop a service while it has active jobs.

## Recommended operation paths

- Existing canvas: context → selected schemas → one apply transaction → undo if
  requested. Execution is a separate, authorized action.
- Existing saved analysis: retrieve route/version → adjust only required inputs
  and parameters → prepare/save if changed → submit → wait → result index.
- New analysis: bounded search → candidate schemas → relevant examples → prepare
  → submit → wait → result index. Preserve the user's resource/execution settings.
- Failed run: brief status → selected log window → resolve the actual error →
  submit a changed request with a new ID, or retry an identical request with its
  original ID. Never restart merely because an acknowledgement was lost.

Generated operator pages are explicitly labelled; they are not scientifically
validated examples. Operator authors should provide purpose, input assumptions,
parameter choices, a tested example, interpretation and limitations alongside
their code/parameter JSON. See [operator documentation](operator_documentation.md).

See [canvas operations](agent_api.md), [headless execution](headless_api.md), and
[third-party API tutorial](api_quickstart.md). Lower payload size is measurable;
actual monetary cost also depends on the client, model, retries and usage pricing.
