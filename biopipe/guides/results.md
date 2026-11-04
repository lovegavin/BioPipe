# Inspect results and hand off native output

Start with `biopipe_artifacts(job_id)` or `biopipe artifacts list <job>`.
The index contains retained artifacts, reports, figures and provenance links.
Use one artifact's metadata/preview when needed; do not load the entire tensor.

An href is an authenticated API path, not a public sharing URL. BioPipe has already
saved the result. Local Studio result links open the retained output. An external
application can fetch the native file through its authenticated client. For an
explicit file handoff: `biopipe artifacts copy <job> <artifact> --role bed --output
handoff/track.bed` (one line). Discover the role in that artifact's preview first.

Figures: `biopipe artifacts figure <job> <report-index> --format svg --figure-id
<id> --output figure.svg`. Select actual IDs/formats from the figures index; omit
figure-id only when unambiguous. Use PDF/SVG or the retained publication PNG,
not a screenshot of the software preview.

Generic numeric NPY output is not a genome track. A domain exporter must preserve
coordinates, assembly, units and file roles before a viewer such as IGV can use it.
Do not invent a conversion or claim a viewer supports BioPipe authentication.
See the api guide for a standalone application client and native-file handoff.
Opening a viewer and scientifically interpreting the result are separate checks.
