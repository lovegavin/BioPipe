# Inspect results and hand off native output

Start with `operon_artifacts(job_id)` or `operon artifacts list <job>`.
The index contains retained artifacts, reports, figures and provenance links.
Use one artifact's metadata/preview when needed; do not load the entire tensor.

An href is an authenticated API path, not a public sharing URL. Operon has already
saved the result. Local Studio result links open the retained output. An external
application can fetch the native file through its authenticated client. For an
explicit file handoff: `operon artifacts copy <job> <artifact> --role bed --output
handoff/track.bed` (one line). Discover the role in that artifact's preview first.

Figures: `operon artifacts figure <job> <report-index> --format svg --figure-id
<id> --output figure.svg`. Select actual IDs/formats from the figures index; omit
figure-id only when unambiguous. Use PDF/SVG or the retained publication PNG,
not a screenshot of the software preview.

Generic numeric NPY output is not a genome track. A domain exporter must preserve
coordinates, assembly, units and file roles before a viewer such as IGV can use it.
Do not invent a conversion or claim a viewer supports Operon authentication.
See the api guide for a standalone application client and native-file handoff.
Opening a viewer and scientifically interpreting the result are separate checks.

Desktop-first handoff: `operon artifacts viewers <job> <artifact> --role <role>`
or `operon_viewer(job_id, artifact_id, role)` lists compatible choices.
Then `operon artifacts open <job> <artifact> --role <role> --viewer <id>` or the
same MCP call with `viewer` launches an installed application (run permission).
`started` means process launch, not successful rendering. `mode=manual` means
open the returned path inside that application. Web entries never upload files
automatically. Remote results are fetched to the client for desktop use.
Use `operon viewers configure <id> --executable <absolute-path>` once if discovery
misses an installation. Configuration belongs to the profile, never the workflow.
The application API exposes the same operations; see `docs/result_viewers.md`.
