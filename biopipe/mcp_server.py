"""MCP stdio adapter; no model provider, credentials or chat implementation."""
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from .client import Client, data_directory


def create_server(client):
    from mcp.server.fastmcp import FastMCP
    from .guidance import guide, instructions
    server = FastMCP("BioPipe", instructions=instructions())

    @server.tool()
    def biopipe_guide(topic: str = 'start', if_sha256: str | None = None) -> dict:
        """Read one installed operating guide: index, start, operators, canvas, workflow, jobs, results or api.

        No analysis or catalog scan. Cache by sha256; if unchanged, content is omitted.
        """
        return guide(topic, if_sha256=if_sha256)

    @server.tool()
    def biopipe_sessions() -> list[dict]:
        """List canvas windows and their activity/selection revision."""
        return client.sessions()

    @server.tool()
    def biopipe_context(session_id: str | None = None, scope: str = "selection") -> dict:
        """Read current selection, neighboring nodes, parameters and info contracts. Call before answering canvas questions."""
        return client.context(session_id, scope)

    @server.tool()
    def biopipe_catalog() -> dict:
        """Compatibility endpoint for the complete catalog. Prefer operator_search and operator_describe for bounded discovery."""
        return client.request("/catalog")

    @server.tool()
    def biopipe_operator_search(query: str = '', kind: str | None = None, category: str | None = None,
                                limit: int = 5, offset: int = 0, view: str = 'brief') -> dict:
        """Search installed operator/Reader summaries without importing implementations or loading all documentation."""
        params = {'query': query, 'kind': kind, 'category': category, 'limit': limit, 'offset': offset, 'view': view}
        return client.request('/v1/operators?' + urlencode({k: v for k, v in params.items() if v is not None}))

    @server.tool()
    def biopipe_operator_describe(ids: list[str], sections: list[str] | None = None, generation: str | None = None,
                                  view: str = 'schema') -> dict:
        """Read schemas/contracts and a document section index for up to 20 IDs. Request named sections or ['*'] explicitly.

        view=schema gives executable schemas, docs gives only identity/document sections, full gives all metadata.
        Use generation from artifact provenance or the full job to read pinned documentation.
        """
        return client.request('/v1/operators/describe', {'ids': ids, 'sections': sections, 'generation': generation, 'view': view})

    @server.tool()
    def biopipe_workflows(workflow_id: str | None = None) -> dict:
        """List saved workflows or retrieve one with its independent frozen parameters; no desktop session required."""
        value = client.request('/v1/workflows' + ('/' + quote(workflow_id, safe='') if workflow_id else ''))
        return value if workflow_id else {'items': value}

    @server.tool()
    def biopipe_workflow_save(graph: dict, workflow_id: str | None = None, expected_version: int | None = None) -> dict:
        """Create or update a saved workflow. Updates require its current version; saving never runs it."""
        return client.request('/v1/workflows', {'graph': graph, 'workflow_id': workflow_id, 'expected_version': expected_version})

    @server.tool()
    def biopipe_workflow_prepare(graph: dict, require_files: bool = True) -> dict:
        """Freeze parameter defaults and validate contracts/files without starting computation. Returns the prepared graph."""
        prepared = client.request('/v1/workflows/prepare', {'graph': graph})
        checked = client.request('/v1/workflows/validate', {'graph': prepared, 'require_files': require_files})
        return {**checked, 'graph': prepared}

    @server.tool()
    def biopipe_submit(request_id: str, graph: dict | None = None, workflow_id: str | None = None,
                       expected_version: int | None = None, view: str = 'brief') -> dict:
        """Submit a workflow without a canvas; requires --allow-run. Exactly one graph or workflow_id.

        Reuse request_id only for identical retries. A saved workflow requires expected_version.
        Returns a durable job ID immediately; closing the MCP connection does not cancel the task.
        """
        payload = {'request_id': request_id, 'expected_version': expected_version}
        if graph is not None:
            payload['graph'] = graph
        if workflow_id:
            payload['workflow_id'] = workflow_id
        from .agent_views import job_view
        job_view({}, view)
        return job_view(client.request('/v1/jobs', payload), view)

    @server.tool()
    def biopipe_jobs() -> dict:
        """List durable task status independently of open windows."""
        return {'items': client.request('/v1/jobs')}

    @server.tool()
    def biopipe_logs(job_id: str, offset: int = 0, limit: int = 4096, encoding: str = 'text') -> dict:
        """Read a small console chunk and byte cursor. encoding=base64 supports exact byte reconstruction; both is explicit."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/logs?' + urlencode({'offset': offset, 'limit': limit, 'encoding': encoding}))

    @server.tool()
    def biopipe_artifacts(job_id: str, artifact_id: str | None = None, preview: bool = False) -> dict:
        """List artifact/report links or inspect one artifact. preview reads a bounded sample, never the whole tensor."""
        path = '/v1/jobs/' + quote(job_id, safe='') + '/artifacts'
        if artifact_id:
            path += '/' + quote(artifact_id, safe='') + ('/preview' if preview else '')
        return client.request(path)

    @server.tool()
    def biopipe_validate(graph: dict) -> dict:
        """Validate a complete route without running it. Missing node positions are automatically laid out."""
        return client.request("/validate", {"graph": graph})

    @server.tool()
    def biopipe_graph(session_id: str) -> dict:
        """Read the complete canvas workspace and its revision."""
        return client.request(f"/sessions/{session_id}")

    @server.tool()
    def biopipe_open(session_id: str, expected_revision: int, graph: dict) -> dict:
        """Open a generated route in a new tab. Does not execute it."""
        return client.request(f"/sessions/{session_id}/open", {"graph": graph, "expected_revision": expected_revision})

    @server.tool()
    def biopipe_apply(session_id: str, document_id: str, expected_revision: int, commands: list[dict], request_id: str) -> dict:
        """Atomically apply add_node, update_node, remove_node, connect, disconnect or configure commands.

        add_node: {op,node}; update_node: {op,id,patch}; remove_node: {op,id};
        connect: {op,edge}; disconnect: {op,id}; configure: {op,patch:{name,memory,base_dir}}.
        One call creates one undo entry. Reuse request_id only when retrying identical commands.
        """
        return client.request(f"/sessions/{session_id}/apply", {"document_id": document_id, "expected_revision": expected_revision,
                              "commands": commands, "request_id": request_id})

    @server.tool()
    def biopipe_undo(session_id: str, document_id: str, expected_revision: int, redo: bool = False) -> dict:
        """Undo or redo one transaction in the shared user/agent edit history."""
        return client.request(f"/sessions/{session_id}/undo", {"document_id": document_id, "expected_revision": expected_revision, "redo": redo})

    @server.tool()
    def biopipe_events(session_id: str, after: int = 0) -> dict:
        """Read semantic changes since an event cursor. If reset=true, re-read context."""
        return client.request(f"/sessions/{session_id}/events?after={after}")

    @server.tool()
    def biopipe_run(session_id: str, document_id: str, expected_revision: int, request_id: str | None = None) -> dict:
        """Run the selected graph only on an explicit user request. Requires --allow-run."""
        return client.request(f"/sessions/{session_id}/run", {"document_id": document_id, "expected_revision": expected_revision,
                                                           **({'request_id': request_id} if request_id else {})})

    @server.tool()
    def biopipe_job(job_id: str, view: str = 'brief', wait_seconds: float = 0) -> dict:
        """Read brief status, or wait internally up to 60 seconds; timeout never cancels/resubmits. view=full restores all details."""
        import math
        from .agent_views import job_view, wait_job
        if not math.isfinite(wait_seconds) or not 0 <= wait_seconds <= 60:
            raise ValueError('wait_seconds must be between 0 and 60')
        job_view({}, view)
        job = client.request('/v1/jobs/' + quote(job_id, safe='') + '?view=' + view)
        return wait_job(client, job, wait_seconds, view=view) if wait_seconds else job

    @server.tool()
    def biopipe_cancel(job_id: str) -> dict:
        """Cancel a running job. Requires --allow-run."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/cancel', {})

    @server.tool()
    def biopipe_plugin_install(wheel: str) -> dict:
        """Install an explicitly selected trusted local plugin wheel. Requires --allow-plugins."""
        return client.request("/plugins/install", {"wheel": wheel})

    @server.resource("biopipe://selection")
    def current_selection() -> str:
        return json.dumps(client.context(), ensure_ascii=False)

    @server.resource('biopipe://guide')
    def operating_guide() -> str:
        return json.dumps(guide(), ensure_ascii=False)

    @server.resource('biopipe://guide/{topic}')
    def operating_topic(topic: str) -> str:
        return json.dumps(guide(topic), ensure_ascii=False)

    @server.resource("biopipe://sessions/{session_id}/selection")
    def selection(session_id: str) -> str:
        return json.dumps(client.context(session_id), ensure_ascii=False)

    @server.resource("biopipe://catalog")
    def catalog_resource() -> str:
        return json.dumps(client.request("/catalog"), ensure_ascii=False)

    return server


def serve(args):
    scopes = ["context"]
    if not args.read_only:
        scopes.append("edit")
    if args.allow_run:
        scopes.append("run")
    if args.allow_plugins:
        scopes.append("plugins")
    from src.web.profile import resolve_profile
    profile = resolve_profile(Path(__file__).resolve().parents[1], profile_dir=args.profile_dir, workspace=args.workspace, data_dir=args.data_dir)
    client = Client(profile.data_dir, instance=args.instance, name="MCP agent", scopes=scopes, auto_start=True, workspace=profile.workspace, require_api=1)
    try:
        create_server(client).run(transport="stdio")
    finally:
        client.close()
