"""Machine-readable CLI. JSON results go to stdout; diagnostics go to stderr."""
import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import quote, urlencode

from .client import Client, ClientError, data_directory


def read_graph_file(path):
    if path is None:
        raise ValueError('A workflow file is required')
    path = Path(path)
    if path.suffix.lower() in ('.yaml', '.yml'):
        from .workflow_spec import load_workflow
        return load_workflow(path)
    if path.suffix.lower() == ".zip":
        from src.web.parameters import import_bundle
        return import_bundle(path.read_bytes()).model_dump(mode="json")
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get('graph', value)


def _wait_job(client, job, timeout, *, view='full', progress=False):
    from .agent_views import wait_job
    previous = None
    def update(current):
        nonlocal previous
        message = f"{current['id']}: {current['status']}"
        if current.get('progress'):
            message += ' ' + json.dumps(current['progress'], ensure_ascii=False)[:240]
        if message != previous:
            print(message, file=sys.stderr, flush=True)
            previous = message
    return wait_job(client, job, timeout, view=view, on_update=update if progress else None)


def parser():
    root = argparse.ArgumentParser(prog="operon", description=__doc__)
    from . import __version__
    root.add_argument('--version', action='version', version='Operon ' + __version__)
    root.add_argument("--profile-dir", type=Path)
    root.add_argument("--workspace", type=Path)
    root.add_argument("--data-dir", type=Path, help="Data directory inside an explicit workspace")
    root.add_argument("--instance")
    root.add_argument("--session")
    root.add_argument("--json", action="store_true", help="JSON is the default output format")
    root.add_argument('--compact', action='store_true', help='Print JSON without indentation')
    commands = root.add_subparsers(dest="command", required=True)
    guide = commands.add_parser('help', aliases=['guide'], help='Read an installed operating guide without starting a service')
    guide.add_argument('topic', nargs='?', default='start')
    guide.add_argument('--if-sha256', help='Omit guide text if this content hash is unchanged')
    serve = commands.add_parser('serve', help='Run the application API without a desktop window')
    serve.add_argument('--port', type=int, default=0, help='Loopback port; 0 selects an available port')
    commands.add_parser('service').add_argument('action', choices=['start', 'status', 'stop'])
    migrate = commands.add_parser("migrate", help="Preview explicit protocol v3 conversion; --apply backs up and writes")
    migrate.add_argument("path", nargs="?", type=Path, help="Graph/workspace JSON, task YAML, or extension Python; omit to migrate the selected profile")
    migrate.add_argument("--manifest", type=Path, help="Old descriptor JSON for Python source conversion")
    migrate.add_argument("--apply", action="store_true")
    registry = commands.add_parser("registry", help="Discover, validate and build repository indexes without a running Studio")
    registry.add_argument("action", choices=["discover", "check", "build"])
    registry.add_argument("--source-ref")
    registry.add_argument("--route-root", action="append")
    registry.add_argument("--output-dir", type=Path)
    registry.add_argument("--scope", choices=["all", "packages", "routes"], default="all")
    commands.add_parser("sessions").add_argument("action", choices=["list"], default="list", nargs="?")
    context = commands.add_parser("context")
    context.add_argument("action", choices=["get"], default="get", nargs="?")
    context.add_argument("--scope", choices=["selection", "document"], default="selection")
    operators = commands.add_parser("operators")
    operators.add_argument("action", choices=["list", "search", "describe"])
    operators.add_argument("id", nargs="?")
    operators.add_argument('--query', default='')
    operators.add_argument('--kind', choices=['operator', 'reader'])
    operators.add_argument('--category')
    operators.add_argument('--limit', type=int, default=5)
    operators.add_argument('--offset', type=int, default=0)
    operators.add_argument('--section', action='append', help='Documentation section; * includes the complete Markdown')
    operators.add_argument('--generation', help='Pinned job plugin generation')
    operators.add_argument('--view', choices=['brief', 'schema', 'docs', 'full'], help='Search defaults to brief; describe defaults to schema')
    workflow = commands.add_parser('workflow', help='Saved workflows independent of canvas sessions')
    workflow.add_argument('action', choices=['init', 'lint', 'format', 'list', 'get', 'save', 'prepare', 'prepare-environment', 'validate', 'export'],
                          help='prepare-environment explicitly authorizes installing this route\'s dependencies; prepare/validate never install')
    workflow.add_argument('value', nargs='?', help='Workflow ID for get; graph/YAML/bundle path for save/prepare/prepare-environment/validate/export')
    workflow.add_argument('--id', help='Existing workflow to update')
    workflow.add_argument('--expected-version', type=int)
    workflow.add_argument('--require-files', action='store_true')
    workflow.add_argument('--output', type=Path)
    workflow.add_argument('--check', action='store_true', help='Check canonical formatting without writing')
    workflow.add_argument('--format', choices=['bundle', 'yaml', 'portable'], default='bundle')
    workflow.add_argument('--template', choices=['csv-pca'], default='csv-pca')
    workflow.add_argument('--runtime-dir', type=Path, help='Prepared relocatable runtime for portable export')
    environment = commands.add_parser('environment', help='Inspect the service runtime or check/prepare a route on its selected hosts')
    environment.add_argument('action', choices=['status', 'check', 'prepare'])
    environment.add_argument('file', nargs='?', type=Path, help='YAML, graph JSON or workflow ZIP for check/prepare')
    environment.add_argument('--require-files', action='store_true', help='Also verify input files during check')
    script = commands.add_parser('script', help='Inspect scripts and extract parameters without executing code')
    script.add_argument('action', choices=['inspect', 'parameters', 'extract', 'package'])
    script.add_argument('path', type=Path)
    script.add_argument('--names', help='Comma-separated explicitly selected parameter names')
    script.add_argument('--output', type=Path, help='Write extracted snapshot JSON; the original script remains unchanged')
    script.add_argument('--id', help='Namespaced operator ID for a promoted package')
    script.add_argument('--title', help='Library label for a promoted package')
    script.add_argument('--category', default='data')
    script.add_argument('--version', default='0.1.0')
    graph = commands.add_parser("graph")
    graph.add_argument("action", choices=["get", "validate", "open", "apply", "undo", "redo", "diff"])
    graph.add_argument("file", nargs="?", type=Path)
    graph.add_argument("--document")
    graph.add_argument("--expected-revision", type=int)
    graph.add_argument("--request-id")
    graph.add_argument('--transaction-id', help='Committed transaction to inspect or conditionally undo/redo')
    graph.add_argument('--offset', type=int, default=0, help='Diff pagination offset')
    graph.add_argument('--limit', type=int, default=20, help='Maximum diff fields (1–50)')
    graph.add_argument("--new-tab", action="store_true", help="Open always creates a new tab")
    events = commands.add_parser("events")
    events.add_argument("action", choices=["watch", "get"], default="watch", nargs="?")
    events.add_argument("--after", type=int, default=0)
    events.add_argument('--limit', type=int, default=20, help='Maximum events per page (1–100); continue at next_cursor')
    run = commands.add_parser("run")
    run.add_argument('file', nargs='?', type=Path, help='Workflow YAML with sidecars, graph JSON, or workflow ZIP')
    run.add_argument('--workflow', help='Saved workflow ID')
    run.add_argument('--expected-version', type=int)
    run.add_argument('--request-id', help='Stable idempotency key for retrying the same submission')
    run.add_argument('--wait', action='store_true')
    run.add_argument('--progress', action='store_true', help='Wait with status changes on stderr; stdout remains JSON')
    run.add_argument('--timeout', type=float, default=0, help='Maximum wait seconds; 0 waits until terminal')
    run.add_argument('--brief', action='store_true', help='Return status/receipt without the full graph and report')
    run.add_argument("--document")
    run.add_argument("--expected-revision", type=int)
    jobs = commands.add_parser("jobs")
    jobs.add_argument("action", choices=["list", "get", "cancel", 'logs', 'wait'])
    jobs.add_argument("id", nargs='?')
    jobs.add_argument('--offset', type=int, default=0)
    jobs.add_argument('--limit', type=int, default=4096)
    jobs.add_argument('--follow', action='store_true')
    jobs.add_argument('--encoding', choices=['text', 'base64', 'both'], default='text')
    jobs.add_argument('--view', choices=['brief', 'full'], default='brief')
    jobs.add_argument('--brief', action='store_true', help='Explicitly select the default brief status view')
    jobs.add_argument('--timeout', type=float, default=30, help='jobs wait timeout; 0 waits until terminal, never cancels')
    artifacts = commands.add_parser('artifacts')
    artifacts.add_argument('action', choices=['list', 'get', 'preview', 'copy', 'report', 'figure', 'viewers', 'open', 'prepare-viewer'])
    artifacts.add_argument('job')
    artifacts.add_argument('id', nargs='?')
    artifacts.add_argument('--output', type=Path)
    artifacts.add_argument('--role')
    artifacts.add_argument('--format')
    artifacts.add_argument('--figure-id')
    artifacts.add_argument('--viewer')
    viewers = commands.add_parser('viewers', help='Discover or configure desktop result viewers')
    viewers.add_argument('action', choices=['list', 'configure', 'default'])
    viewers.add_argument('id', nargs='?')
    viewers.add_argument('--executable', help='Absolute executable/GUI JAR path; omit to clear a configured path')
    viewers.add_argument('--refresh', action='store_true')
    viewers.add_argument('--viewer', help='Default desktop viewer ID; omit to restore automatic selection')
    servers = commands.add_parser('servers')
    servers.add_argument('action', choices=['list', 'save', 'connect', 'trust'])
    servers.add_argument('value', nargs='?')
    servers.add_argument('--credentials-stdin', action='store_true', help='Read password/passphrase JSON from stdin; never command arguments')
    servers.add_argument('--fingerprint')
    plugin = commands.add_parser("plugin")
    plugin.add_argument("action", choices=["init", "check", "test", "build", "export-library", "install", "list", "refresh", "declarations", "remove", "enable", "disable", "restore"])
    plugin.add_argument("path", nargs="?")
    plugin.add_argument("--library-version", default="1.0.0")
    plugin.add_argument("--template", choices=["operator", "reader"], default="operator")
    schema = commands.add_parser("schema")
    schema.add_argument("name", choices=["operator", "package", "graph", "workspace", "workflow"])
    mcp = commands.add_parser("mcp")
    mcp.add_argument("--allow-run", action="store_true")
    mcp.add_argument("--read-only", action="store_true")
    mcp.add_argument("--allow-plugins", action="store_true")
    return root


def execute(args):
    # Shell-relative selectors must be resolved before the shared profile policy
    # (whose relative paths are intentionally anchored to the application/home).
    if args.workspace is not None:
        args.workspace = args.workspace.expanduser().resolve()
    if args.command == 'run' and args.progress:
        args.wait = True
    if args.command == 'script':
        from .script_operators import inspect_script, parameter_candidates, extract_parameters, validate_script, export_script_package
        if args.path.suffix.lower() == '.json':
            document = json.loads(args.path.read_text(encoding='utf-8-sig'))
            snapshot = validate_script(document.get('script', document))
        else:
            snapshot = inspect_script(args.path)
        if args.action == 'package':
            if not args.output or not args.id or not args.title:
                raise ValueError('script package requires --output, --id and --title')
            return export_script_package(snapshot, args.output, operator_id=args.id, title=args.title,
                                         category=args.category, version=args.version)
        if args.action == 'inspect':
            return snapshot
        if args.action == 'parameters':
            if snapshot['language'] != 'python':
                raise ValueError('Automatic parameter candidates currently support Python')
            return {'candidates': parameter_candidates(snapshot['code'])}
        result = extract_parameters(snapshot, (args.names or '').split(','))
        if args.output:
            from src.web.storage import atomic_json
            atomic_json(args.output, result)
        return result
    if args.command == 'workflow' and args.action in ('init', 'lint', 'format'):
        from .workflow_spec import init_workflow, load_workflow, format_workflow
        if not args.value:
            raise ValueError('A workflow file or project directory is required')
        if args.action == 'init':
            return init_workflow(args.value)
        if args.action == 'format':
            return format_workflow(args.value, check=args.check)
        graph = load_workflow(args.value)
        return {'valid': True, 'nodes': len(graph['nodes']), 'edges': len(graph['edges']), 'name': graph['name']}
    if args.command == 'run' or args.command == 'jobs' and args.action == 'wait':
        import math
        if not math.isfinite(args.timeout) or args.timeout < 0:
            raise ValueError('timeout must be a finite non-negative number')
    if args.command in ('help', 'guide'):
        from .guidance import guide
        return guide(args.topic, if_sha256=args.if_sha256)
    if args.command == 'serve':
        from .headless import serve
        return serve(profile_dir=args.profile_dir, workspace=args.workspace, data_dir=args.data_dir, port=args.port)
    if args.command == "migrate":
        from .migrate import migrate
        return migrate(path=args.path, profile_dir=args.profile_dir, workspace=args.workspace,
                       data_dir=args.data_dir, manifest=args.manifest, apply=args.apply)
    if args.command == "registry":
        from .registry import inventory, maintain
        if args.source_ref and args.action != "discover":
            raise ValueError("--source-ref is for static discovery only")
        os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
        roots = [str(Path(path).resolve()) for path in args.route_root] if args.route_root else None
        return inventory(source_ref=args.source_ref, route_roots=roots) if args.action == "discover" else maintain(
            args.action, route_roots=roots, output_dir=args.output_dir, scope=args.scope)
    if args.command == "schema":
        if args.name == 'workflow':
            from .workflow_spec import json_schema
            return json_schema()
        from biopipe_sdk.protocol import Descriptor, PackageDescriptor
        from src.web.models import Graph, Workspace
        return {"operator": Descriptor, "package": PackageDescriptor, "graph": Graph, "workspace": Workspace}[args.name].model_json_schema()
    if args.command == "plugin":
        from . import developer
        from .plugins import PluginManager, run_process
        if args.action == "init":
            return developer.scaffold(args.path, args.template)
        if args.action == "check":
            return json.loads(run_process([sys.executable, "-m", "biopipe.developer", "check", Path(args.path).resolve()]))
        if args.action == "test":
            path = Path(args.path).resolve()
            environment = dict(os.environ, PYTHONPATH=os.pathsep.join([str(path), str(path / "src"), str(Path(__file__).resolve().parents[1])]))
            output = run_process([sys.executable, "-m", "pytest", "-q", path / "tests"], env=environment)
            return {"passed": True, "output": output}
        if args.action == "build":
            return developer.build(args.path)
        manager = PluginManager(data_directory(args.profile_dir, args.workspace, args.data_dir))
        if args.action == 'export-library':
            from .library_bundle import build_bundle
            manager.ensure_source_root()
            return build_bundle(manager.source_root, args.path or '.', args.library_version)
        if args.action == "list":
            from .source_library import directories
            return {**manager.state(), "inbox": str(manager.inbox),
                    "source_directories": {kind: str(path) for kind, path in directories(manager.source_root).items()}}
        if args.action == "declarations":
            return manager.update_declarations(json.loads(Path(args.path).read_text(encoding="utf-8")))
        if args.action == "refresh":
            return manager.refresh()
        if args.action in {"enable", "disable", "restore"}:
            return manager.manage(args.path, args.action)
        return manager.install(args.path, remove=args.path if args.action == "remove" else None)
    if args.command == "mcp":
        from .mcp_server import serve
        return serve(args)
    graph_file = (args.value if args.command == 'workflow' and args.action not in ('list', 'get')
                  else args.file if args.command in ('run', 'environment') else None)
    # Reject malformed/missing projects before creating a persistent service.
    graph_value = read_graph_file(graph_file) if graph_file is not None else None
    if args.command == 'environment' and args.action != 'status' and graph_value is None:
        raise ValueError('environment check/prepare requires a workflow file')
    scopes = ["context", "edit"]
    if (args.command == 'workflow' and args.action == 'prepare-environment'
            or args.command == 'environment' and args.action == 'prepare'):
        if graph_value is None:
            raise ValueError('workflow prepare-environment requires a graph, YAML or bundle file')
        scopes.append('plugins')
    if (args.command == 'viewers' and args.action in ('configure', 'default')
            or args.command == 'artifacts' and args.action in ('open', 'prepare-viewer')):
        scopes.append('run')
    if args.command == 'run' or args.command == 'jobs' and args.action == 'cancel' or args.command == 'service' and args.action == 'stop' or args.command == 'servers' and args.action == 'connect':
        scopes.append("run")
    directory = data_directory(args.profile_dir, args.workspace, args.data_dir)
    from src.web.profile import resolve_profile
    profile = resolve_profile(Path(__file__).resolve().parents[1], profile_dir=args.profile_dir, workspace=args.workspace, data_dir=args.data_dir)
    if args.command == 'service' and args.action == 'status':
        from .client import instances
        return {'instances': [{k: v for k, v in instance.items() if k != 'secret'} for instance in instances(directory)]}
    client = Client(directory, instance=args.instance, name="Operon CLI", scopes=scopes,
                    auto_start=not (args.command == 'service' and args.action == 'stop'), workspace=profile.workspace,
                    require_api=1 if args.command in ('operators', 'workflow', 'environment', 'jobs', 'artifacts', 'servers', 'service', 'viewers') or args.command == 'run' and (args.file or args.workflow) else 0)
    try:
        if args.command == 'environment':
            if args.action == 'status':
                return client.request('/v1/environment')
            payload = {'graph': graph_value}
            if args.action == 'check':
                payload['require_files'] = args.require_files
            return client.request('/v1/workflows/' + ('validate' if args.action == 'check' else 'prepare-environment'), payload)
        if args.command == 'service':
            return client.request('/v1/service/stop', {}) if args.action == 'stop' else client.request('/v1/service')
        if args.command == 'workflow':
            if args.action == 'list':
                return client.request('/v1/workflows')
            if args.action == 'get':
                return client.request('/v1/workflows/' + quote(args.value or '', safe=''))
            graph = graph_value
            payload = {'graph': graph}
            if args.action == 'save':
                payload.update(workflow_id=args.id, expected_version=args.expected_version)
                return client.request('/v1/workflows', payload)
            if args.action == 'export':
                if not args.output:
                    raise ValueError('workflow export requires --output')
                if args.format in ('yaml', 'portable'):
                    prepared = client.request('/v1/workflows/prepare', payload)
                    if args.format == 'yaml':
                        from .workflow_spec import export_workflow
                        return export_workflow(prepared, args.output)
                    from .portable import export_portable
                    return export_portable(prepared, args.output, runtime_dir=args.runtime_dir)
                return client.download('/v1/workflows/export', args.output, payload)
            if args.action == 'validate':
                payload['require_files'] = args.require_files
            result = client.request('/v1/workflows/' + args.action, payload)
            if args.action == 'prepare':
                client.request('/v1/workflows/validate', {'graph': result, 'require_files': args.require_files})
                if args.output:
                    if args.format == 'yaml':
                        from .workflow_spec import export_workflow
                        export_workflow(result, args.output)
                    else:
                        from src.web.storage import atomic_json
                        args.output.parent.mkdir(parents=True, exist_ok=True)
                        atomic_json(args.output, result)
            return result
        if args.command == 'run' and (args.file or args.workflow):
            if args.document or (args.file and args.workflow):
                raise ValueError('Choose a file, a saved workflow, or a canvas document, not multiple sources')
            payload = {'graph': graph_value} if args.file else {'workflow_id': args.workflow, 'expected_version': args.expected_version}
            if args.request_id:
                payload['request_id'] = args.request_id
            job = client.request('/v1/jobs', payload)
            from .agent_views import job_view
            view = 'brief' if args.brief else 'full'
            return _wait_job(client, job, args.timeout, view=view, progress=args.progress) if args.wait else job_view(job, view)
        if args.command == 'run' and not args.document:
            raise ValueError('run requires a workflow file, --workflow, or --document with --expected-revision')
        if args.command == 'viewers':
            if args.action == 'list':
                return client.request('/v1/viewers' + ('?refresh=true' if args.refresh else ''))
            if args.action == 'default':
                if not args.id:
                    raise ValueError('A file extension is required, for example .hic')
                return client.request('/v1/viewers/default', {'extension': args.id, 'viewer': args.viewer})
            if not args.id:
                raise ValueError('A viewer ID is required')
            return client.request('/v1/viewers/' + quote(args.id, safe='') + '/configure', {'executable': args.executable})
        if args.command == 'artifacts':
            prefix = '/v1/jobs/' + quote(args.job, safe='')
            if args.action == 'list':
                return client.request(prefix + '/artifacts')
            if not args.id:
                raise ValueError('An artifact ID or report index is required')
            if args.action in ('viewers', 'open', 'prepare-viewer'):
                if not args.role:
                    raise ValueError('A retained file --role is required')
                path = prefix + '/artifacts/' + quote(args.id, safe='')
                if args.action == 'viewers':
                    return client.request(path + '/viewers?' + urlencode({'role': args.role}))
                if args.action == 'open':
                    return client.request(path + '/open-viewer', {'role': args.role, 'viewer': args.viewer})
                return client.request(path + '/prepare-viewer', {'role': args.role})
            if args.action in ('report', 'figure'):
                path = prefix + '/reports/' + str(int(args.id))
                if args.action == 'figure':
                    path += '/figure?' + urlencode({k: v for k, v in {'format': args.format, 'figure_id': args.figure_id}.items() if v})
            else:
                path = prefix + '/artifacts/' + quote(args.id, safe='')
                if args.action == 'preview':
                    path += '/preview'
                elif args.action == 'copy':
                    path += '/file' + ('?' + urlencode({'role': args.role}) if args.role else '')
                if args.action in ('get', 'preview'):
                    return client.request(path)
            if not args.output:
                raise ValueError('Copying an artifact/report/figure requires --output')
            return client.download(path, args.output)
        if args.command == 'servers':
            if args.action == 'list':
                return client.request('/v1/remotes')
            if args.action == 'save':
                return client.request('/v1/remotes', json.loads(Path(args.value).read_text(encoding='utf-8')))
            payload = {'fingerprint': args.fingerprint} if args.action == 'trust' else (json.load(sys.stdin) if args.credentials_stdin else {})
            return client.request('/v1/remotes/' + quote(args.value or '', safe='') + '/' + args.action, payload)
        if args.command == "sessions":
            return client.sessions()
        if args.command == "operators":
            if args.action == 'list':
                # Preserve the original CLI catalog shape for existing scripts;
                # search is the bounded, agent-oriented discovery operation.
                return client.request('/catalog')
            if args.action == 'describe':
                if not args.id:
                    raise ValueError('operators describe requires an operator/Reader ID')
                result = client.request('/v1/operators/describe', {'ids': args.id.split(','), 'sections': args.section,
                                        'generation': args.generation, 'view': args.view or 'schema'})
                if len(result['items']) == 1:
                    item = result['items'][0]
                    return {**item['descriptor'], 'documentation': item['documentation'], 'generation': result['generation']}
                return result
            query = {'query': args.query or (args.id or ''), 'limit': args.limit, 'offset': args.offset, 'view': args.view or 'brief'}
            query.update({k: v for k, v in {'kind': args.kind, 'category': args.category}.items() if v})
            return client.request('/v1/operators?' + urlencode(query))
        if args.command == "context":
            return client.context(args.session, args.scope)
        if args.command == "jobs":
            if args.action == 'list':
                return client.request('/v1/jobs')
            if not args.id:
                raise ValueError('A job ID is required')
            path = '/v1/jobs/' + quote(args.id, safe='')
            if args.action == 'logs':
                cursor = args.offset
                while True:
                    value = client.request(path + '/logs?' + urlencode({'offset': cursor, 'limit': args.limit, 'encoding': args.encoding}))
                    if not args.follow:
                        return value
                    print(json.dumps(value, ensure_ascii=False), flush=True)
                    cursor = value['offset']
                    if value['done']:
                        return None
                    time.sleep(.4)
            from .agent_views import job_view
            view = 'brief' if args.brief else args.view
            if args.action == 'cancel':
                return job_view(client.request(path + '/cancel', {}), view)
            job = client.request(path + '?view=' + view)
            return _wait_job(client, job, args.timeout, view=view) if args.action == 'wait' else job
        if args.command == "graph" and args.action == "validate":
            return client.request("/validate", {"graph": read_graph_file(args.file)})
        session = client.session(args.session)
        if args.command == "events":
            cursor = args.after
            while True:
                result = client.request(f"/sessions/{session}/events?" + urlencode({'after': cursor, 'limit': args.limit}))
                if args.action == "get":
                    return result
                if result["reset"]:
                    print(json.dumps({"type": "reset", "seq": result["seq"]}), flush=True)
                for event in result["events"]:
                    print(json.dumps(event, ensure_ascii=False), flush=True)
                cursor = result.get('next_cursor', result['seq'])
                time.sleep(.35)
        if args.command == "graph" and args.action == "get":
            snapshot = client.request(f"/sessions/{session}")
            if args.document:
                return next(doc for doc in snapshot["workspace"]["documents"] if doc["id"] == args.document)
            return snapshot
        if args.command == 'graph' and args.action == 'diff':
            if not args.transaction_id:
                raise ValueError('graph diff requires --transaction-id from an edit receipt or event')
            return client.request(f'/sessions/{session}/transactions/' + quote(args.transaction_id, safe='') + '?'
                                  + urlencode({'offset': args.offset, 'limit': args.limit}))
        if args.expected_revision is None:
            raise ClientError("Edits require --expected-revision from the context snapshot", "revision_required")
        payload = {"expected_revision": args.expected_revision, "document_id": args.document}
        if args.command == "run":
            if args.request_id:
                payload['request_id'] = args.request_id
            job = client.request(f"/sessions/{session}/run", payload)
            from .agent_views import job_view
            view = 'brief' if args.brief else 'full'
            return _wait_job(client, job, args.timeout, view=view, progress=args.progress) if args.wait else job_view(job, view)
        if args.action == "open":
            payload["graph"] = read_graph_file(args.file)
        elif args.action == "apply":
            value = json.loads(args.file.read_text(encoding="utf-8"))
            payload.update(commands=value if isinstance(value, list) else value["commands"], request_id=args.request_id)
        elif args.action == "redo":
            payload["redo"] = True
        if args.action in ('undo', 'redo') and args.transaction_id:
            payload['transaction_id'] = args.transaction_id
        return client.request(f"/sessions/{session}/{'undo' if args.action == 'redo' else args.action}", payload)
    finally:
        client.close()


def main(argv=None):
    from .installation import configure_environment
    configure_environment(Path(__file__).resolve().parents[1])
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    # Accept common global selectors anywhere, including after a subcommand.
    argv = list(sys.argv[1:] if argv is None else argv)
    global_args, rest = [], []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in ("--profile-dir", "--workspace", "--data-dir", "--instance", "--session") and index + 1 < len(argv):
            global_args.extend(argv[index:index+2]); index += 2
        elif item in ('--json', '--compact'):
            global_args.append(item); index += 1
        else:
            rest.append(item); index += 1
    args = parser().parse_args(global_args + rest)
    try:
        # MCP and JSONL streams own stdout; imports/calculation logs elsewhere
        # are redirected so clients always receive a parseable JSON document.
        if args.command in ('mcp', 'events', 'serve') or args.command == 'jobs' and args.action == 'logs' and args.follow:
            result = execute(args)
        else:
            with redirect_stdout(sys.stderr):
                result = execute(args)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=None if args.compact else 2,
                             **({'separators': (',', ':')} if args.compact else {})))
            if args.command == "registry" and (result["errors"] or (args.action == "check" and result["changed"])):
                raise SystemExit(1)
            if args.command == 'workflow' and args.action == 'format' and args.check and result['changed']:
                raise SystemExit(1)
            if ((args.command == 'workflow' and args.action in ('validate', 'prepare-environment')
                 or args.command == 'environment' and args.action in ('check', 'prepare'))
                    and result.get('readiness', {}).get('status') != 'ready'):
                raise SystemExit(1)
            if args.command == 'run' and args.wait or args.command == 'jobs' and args.action == 'wait':
                if result.get('wait_timed_out'):
                    raise SystemExit(124)
                if result.get('status') not in ('complete',):
                    raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        if args.command == 'serve':
            import traceback
            traceback.print_exc(file=sys.stderr)
        code = getattr(error, "code", "invalid_request")
        print(json.dumps({"error": {"code": code, "message": str(error), "details": getattr(error, "details", None)}}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(3 if code == "revision_conflict" else 4 if code in ("not_connected", "ambiguous_session", "no_active_session") else 2)
