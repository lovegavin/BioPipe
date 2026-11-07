# Connect an application to Operon: a practical API tutorial

Two integration directions use the same API:

1. **An application drives Operon**: prepare/validate a workflow, submit a task,
   monitor it and retrieve results. No desktop or MCP/model is required.
2. **Operon hands results to a specialist tool**: select a retained native output,
   then open that format in the external tool. A domain exporter supplies correct
   coordinates, units and metadata. The API is not a universal format converter.

For example, IGV uses native genome tracks; R/Python plotting can consume suitable
tables; illustration tools can open retained PDF/SVG. Check the target tool's
supported formats. Operon does not remotely control arbitrary applications.

For an implemented desktop-first handoff, see [result viewers](result_viewers.md):
discover compatible installed apps, configure their executable once, and open a
retained file through `/api/v1/jobs/{job}/artifacts/{id}/open-viewer`. This tutorial
still applies to third-party clients that prefer to fetch files themselves.

## 1. Choose the workspace and start/discover the service

Install Operon into the Python environment used by your integration. With a
source checkout: `python -m pip install -e .`. Choose an explicit project directory
containing the inputs; use the same workspace/profile for every call.

```text
operon --workspace project service start
operon help api
```

`service start` is optional with Python's `auto_start=True`. It starts/reuses an
authenticated loopback service on a dynamically selected port. There is no fixed
port or developer-machine directory to copy. For an existing default Studio
profile, omit workspace and use `data_directory()` so the integration sees its jobs.

## 2. Connect using the Python transport

```python
from pathlib import Path
from operon.client import Client, data_directory

workspace = Path("project").resolve()
client = Client(data_directory(workspace=workspace), workspace=workspace,
                name="my-analysis-tool", scopes=["context", "run"],
                auto_start=True, require_api=1)
try:
    capabilities = client.request("/v1/capabilities")
    reference = client.request("/v1/openapi.json")
    # Perform the requests below here, before closing the client.
finally:
    client.close()
```

`context` permits reads/preparation/validation; `run` permits submitting/cancelling;
`edit` is additionally required to save workflows or edit canvases. The client
handles discovery and the credential exchange. Do not print client tokens or
discovery records. `close()` disconnects this client, not the service or running jobs.

The full HTTP prefix is `/api/v1`. `Client.request()` takes `/v1/...` and adds
`/api` itself. Returned artifact hrefs include `/api`; remove it before passing
them to `Client.download`. Examples below show code inside an authenticated session.

## 3. Discover only the needed operator contract

```python
found = client.request("/v1/operators?query=describe&limit=3&view=brief")
spec = client.request("/v1/operators/describe", {
    "ids": ["describe"], "view": "schema"
})
```

For an existing saved route use GET `/v1/workflows` and `/v1/workflows/{id}`.
Prefer its frozen values over the library's current defaults. For a new route,
the [installed workflow guide](../operon/guides/workflow.md) includes a minimal
CSV-to-summary graph. `operon schema graph` returns the exact graph JSON schema.

For the runnable example, create `project/input.csv` containing:

```csv
a,b
1,2
3,4
```

Save this graph as `project/route.json`:

```json
{"schema_version":2,"name":"CSV summary","base_dir":".",
 "nodes":[
   {"id":"input","kind":"source","source":{"path":"input.csv","dims":["sample","feature"],"labels":{"sample":"auto","feature":"builtin"}}},
   {"id":"summary","kind":"operator","operator":"describe","params":{}}
 ],"edges":[{"id":"e1","source":"input","target":"summary"}]}
```

Input paths
are resolved relative to graph.base_dir in the selected workspace; the example
uses `base_dir="."`. The route's memory and execution settings remain authoritative.

## 4. Prepare, validate and submit

```python
import json
graph = json.loads(Path("project/route.json").read_text(encoding="utf-8"))
prepared = client.request("/v1/workflows/prepare", {"graph": graph})
client.request("/v1/workflows/validate", {"graph": prepared, "require_files": True})
receipt = client.request("/v1/jobs", {
    "graph": prepared, "request_id": "my-analysis-001"
})
job_id = receipt["id"]
```

An accepted submission is not a finished analysis. Retries of the identical request
must reuse its request_id; changed parameters need a new one. Persist the receipt.
Prepared defaults/pins and every job's parameter JSON are independent snapshots.
Saved workflows may instead be submitted by workflow_id plus expected_version.

## 5. Wait, inspect results and preserve provenance

```python
from operon.agent_views import wait_job
job = wait_job(client, receipt, timeout=60, view="brief")
if job.get("wait_timed_out"):
    print("Still running:", job["id"])  # reconnect later; do not resubmit
elif job["status"] != "complete":
    error = client.request(f"/v1/jobs/{job_id}/logs?limit=4096&encoding=text")
else:
    index = client.request(f"/v1/jobs/{job_id}/artifacts")
    parameters = client.request(f"/v1/jobs/{job_id}/parameters")
```

`index` lists artifacts, reports, figures and provenance, without loading matrices.
The API preserves the existing local/SSH memory admission, spill and transfer
mechanisms. A retained href can be fetched repeatedly; it does not rerun analysis.
An unavailable/deleted output is not silently recreated.

## 6. Open a native output in the other software

The result is already saved in Operon. If the other program can authenticate, it
can fetch the returned link with the same Bearer token. A normal browser or viewer
does not inherit that token. For a viewer that expects a local file, copy only the
chosen output through the streaming client:

```python
report = index["reports"][0]  # choose an actual returned report
client.download(report["href"].removeprefix("/api"), Path("handoff/summary.json"))
# For a figure, select its actual id/format from index["figures"], then use its href.
# For a multi-file artifact, preview it and select a declared role such as bed.
```

Remote jobs retain computation/data on the server; requesting a local native file
explicitly transfers that selected output. Never put a token in a query string or
shareable handoff file. A generic numeric NPY tensor lacks genome coordinate
semantics: use the [IGV exporter and acceptance example](../examples/igv_handoff/README.md)
to obtain BED/bedGraph/provenance, then open the session or tracks in IGV. This
tutorial's summary JSON demonstrates transport, not a genome-track conversion.

## Run the complete client example

From the checkout, with Operon installed:

```text
python examples/api_client/run_workflow.py --workspace project --workflow project/route.json --request-id my-analysis-001
python examples/api_client/run_workflow.py --workspace project --job <returned-id>
python examples/api_client/run_workflow.py --workspace project --job <returned-id> --href <exact-returned-href> --output handoff/summary.json
```

The first command prepares, validates and runs. The second only reads the existing
task. The third copies a selected retained output. `--role` selects a native file
role. The script emits no credentials, never stops a shared service, and returns
124 on a timed-out wait, 1 on failed/cancelled/interrupted tasks, 0 otherwise.
See [the example source](../examples/api_client/run_workflow.py).

## Non-Python clients and the reference schema

1. Resolve the same profile data directory. Read its local `agent/servers/*.json`
   discovery record. Validate the loopback URL and instance identity as the Python
   client does; do not copy a stale port into a permanent configuration.
2. POST `/api/agent/connect`, header `X-Operon-Bridge: <local-discovery-secret>`,
   JSON `{"name":"my-tool","scopes":["context","run"]}`.
3. Use `Authorization: Bearer <returned-token>` for every request, including
   GET `/api/v1/capabilities`, `/api/v1/openapi.json` and output-file links.
4. POST `/api/agent/disconnect` with the bearer token when finished.

OpenAPI is authenticated and limited to application endpoints. `/openapi.json`
remains disabled. Authentication/discovery is local: this is not a public,
multi-user service. Use Operon's existing SSH execution instead of exposing the
loopback API to the network. No global permission change is needed for the example.

## Errors to handle explicitly

| Condition | Action |
| --- | --- |
| 403 / missing scope | Reconnect with the permissions authorized for this task |
| revision_conflict | Retrieve the latest saved route/canvas revision before editing |
| idempotency_conflict | Keep one request ID tied to one immutable submission |
| submission_uncertain | Inspect task history before considering another submission |
| invalid_request / validation error | Correct fields, paths or contracts before retrying |
| Wait timeout / lost connection | Reconnect to the known job; do not assume cancellation |
| Missing retained file | Report it; do not silently recompute or guess a disk path |

For the endpoint reference see [Application API](headless_api.md); for model-driven
use see [the three-layer agent guide](agent_operations.md).
