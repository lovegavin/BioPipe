"""Machine-readable CLI. JSON results go to stdout; diagnostics go to stderr."""
import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import time

from .client import Client, ClientError, data_directory


def parser():
    root = argparse.ArgumentParser(prog="biopipe", description=__doc__)
    root.add_argument("--profile-dir", type=Path)
    root.add_argument("--workspace", type=Path)
    root.add_argument("--data-dir", type=Path, help="Data directory inside an explicit workspace")
    root.add_argument("--instance")
    root.add_argument("--session")
    root.add_argument("--json", action="store_true", help="JSON is the default output format")
    commands = root.add_subparsers(dest="command", required=True)
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
    operators.add_argument("action", choices=["list", "describe"])
    operators.add_argument("id", nargs="?")
    graph = commands.add_parser("graph")
    graph.add_argument("action", choices=["get", "validate", "open", "apply", "undo", "redo"])
    graph.add_argument("file", nargs="?", type=Path)
    graph.add_argument("--document")
    graph.add_argument("--expected-revision", type=int)
    graph.add_argument("--request-id")
    graph.add_argument("--new-tab", action="store_true", help="Open always creates a new tab")
    events = commands.add_parser("events")
    events.add_argument("action", choices=["watch", "get"], default="watch", nargs="?")
    events.add_argument("--after", type=int, default=0)
    run = commands.add_parser("run")
    run.add_argument("--document", required=True)
    run.add_argument("--expected-revision", type=int, required=True)
    jobs = commands.add_parser("jobs")
    jobs.add_argument("action", choices=["get", "cancel"])
    jobs.add_argument("id")
    plugin = commands.add_parser("plugin")
    plugin.add_argument("action", choices=["init", "check", "test", "build", "install", "list", "refresh", "remove", "enable", "disable", "restore"])
    plugin.add_argument("path", nargs="?")
    plugin.add_argument("--template", choices=["operator", "reader"], default="operator")
    schema = commands.add_parser("schema")
    schema.add_argument("name", choices=["operator", "package", "graph", "workspace"])
    mcp = commands.add_parser("mcp")
    mcp.add_argument("--allow-run", action="store_true")
    mcp.add_argument("--read-only", action="store_true")
    mcp.add_argument("--allow-plugins", action="store_true")
    return root


def execute(args):
    if args.command == "registry":
        from .registry import inventory, maintain
        if args.source_ref and args.action != "discover":
            raise ValueError("--source-ref is for static discovery only")
        os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
        return inventory(source_ref=args.source_ref, route_roots=args.route_root) if args.action == "discover" else maintain(
            args.action, route_roots=args.route_root, output_dir=args.output_dir, scope=args.scope)
    if args.command == "schema":
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
        if args.action == "list":
            from .source_library import directories
            return {**manager.state(), "inbox": str(manager.inbox),
                    "source_directories": {kind: str(path) for kind, path in directories(manager.source_root).items()}}
        if args.action == "refresh":
            return manager.refresh()
        if args.action in {"enable", "disable", "restore"}:
            return manager.manage(args.path, args.action)
        return manager.install(args.path, remove=args.path if args.action == "remove" else None)
    if args.command == "mcp":
        from .mcp_server import serve
        return serve(args)
    scopes = ["context", "edit"]
    if args.command in ("run", "jobs"):
        scopes.append("run")
    client = Client(data_directory(args.profile_dir, args.workspace, args.data_dir), instance=args.instance, name="BioPipe CLI", scopes=scopes)
    try:
        if args.command == "sessions":
            return client.sessions()
        if args.command == "operators":
            catalog = client.request("/catalog")
            if args.action == "list":
                return catalog
            item = next((item for item in [*catalog["operators"], *catalog["readers"]] if item["id"] == args.id), None)
            if item is None:
                raise ClientError("Unknown operator or reader", "not_found")
            return item
        if args.command == "context":
            return client.context(args.session, args.scope)
        if args.command == "jobs":
            return client.request(f"/jobs/{args.id}" + ("/cancel" if args.action == "cancel" else ""), {} if args.action == "cancel" else None)
        if args.command == "graph" and args.action == "validate":
            return client.request("/validate", {"graph": json.loads(args.file.read_text(encoding="utf-8"))})
        session = client.session(args.session)
        if args.command == "events":
            cursor = args.after
            while True:
                result = client.request(f"/sessions/{session}/events?after={cursor}")
                if args.action == "get":
                    return result
                if result["reset"]:
                    print(json.dumps({"type": "reset", "seq": result["seq"]}), flush=True)
                for event in result["events"]:
                    print(json.dumps(event, ensure_ascii=False), flush=True)
                cursor = result["seq"]
                time.sleep(.35)
        if args.command == "graph" and args.action == "get":
            snapshot = client.request(f"/sessions/{session}")
            if args.document:
                return next(doc for doc in snapshot["workspace"]["documents"] if doc["id"] == args.document)
            return snapshot
        if args.expected_revision is None:
            raise ClientError("Edits require --expected-revision from the context snapshot", "revision_required")
        payload = {"expected_revision": args.expected_revision, "document_id": args.document}
        if args.command == "run":
            return client.request(f"/sessions/{session}/run", payload)
        if args.action == "open":
            payload["graph"] = json.loads(args.file.read_text(encoding="utf-8"))
        elif args.action == "apply":
            value = json.loads(args.file.read_text(encoding="utf-8"))
            payload.update(commands=value if isinstance(value, list) else value["commands"], request_id=args.request_id)
        elif args.action == "redo":
            payload["redo"] = True
        return client.request(f"/sessions/{session}/{'undo' if args.action == 'redo' else args.action}", payload)
    finally:
        client.close()


def main(argv=None):
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
        elif item == "--json":
            global_args.append(item); index += 1
        else:
            rest.append(item); index += 1
    args = parser().parse_args(global_args + rest)
    try:
        # MCP and JSONL streams own stdout; imports/calculation logs elsewhere
        # are redirected so clients always receive a parseable JSON document.
        if args.command == "mcp" or args.command == "events":
            result = execute(args)
        else:
            with redirect_stdout(sys.stderr):
                result = execute(args)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
            if args.command == "registry" and (result["errors"] or (args.action == "check" and result["changed"])):
                raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        code = getattr(error, "code", "invalid_request")
        print(json.dumps({"error": {"code": code, "message": str(error), "details": getattr(error, "details", None)}}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(3 if code == "revision_conflict" else 4 if code in ("not_connected", "ambiguous_session") else 2)
