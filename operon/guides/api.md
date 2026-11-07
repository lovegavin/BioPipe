# Connect a third-party application

The HTTP API is the integration surface; no MCP/model or desktop is needed.
In Python use `operon.client.Client` to discover a dynamic loopback port,
authenticate and optionally start the service. Keep the same workspace/profile.

```python
from pathlib import Path
from operon.client import Client, data_directory

workspace = Path("project").resolve()  # choose your actual input/project directory
client = Client(data_directory(workspace=workspace), workspace=workspace,
                name="my-viewer", scopes=["context"], auto_start=True, require_api=1)
try:
    capabilities = client.request("/v1/capabilities")
    topics = client.request("/v1/guides")
    # Use the real job ID from a submission or the task list.
    jobs = client.request("/v1/jobs")
finally:
    client.close()
```

For execution explicitly request context/run; saving/editing also needs edit.
Prepare, validate, submit with a stable request_id, check terminal status, then
GET /api/v1/jobs/{id}/artifacts. Use the returned href for a selected native file.
`Client.request` / `Client.download` accept `/v1/...` paths, not `/api/v1/...`.
`Client.download(path, destination)` streams to disk without materializing data.

API reference: authenticated GET /api/v1/openapi.json; capability discovery:
GET /api/v1/capabilities. Non-Python clients use the local discovery record and
POST /api/agent/connect with X-Operon-Bridge, then a Bearer token. Never put these
credentials in a viewer URL, prompt or shared manifest. The service is local,
not a public multi-user API. Use Operon's SSH execution for remote computation.

A viewer that cannot send authentication headers should open an explicitly
exported native file. For genome tracks use the existing IGV exporter example;
for statistical plotting use suitable tables/native figures. Each tool still
needs its expected format, coordinates and metadata. There is no universal
adapter that makes every application understand arbitrary Operon tensors.

Source checkout: docs/api_quickstart.md and examples/api_client/run_workflow.py
provide the complete prepare/run/result-handoff walkthrough. This installed guide
and OpenAPI remain available even without the source repository.
