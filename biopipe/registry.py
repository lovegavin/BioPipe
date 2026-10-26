"""Explicit, reproducible registry maintenance; never run during GUI startup.

Local source discovery imports trusted repository code. Upstream discovery only
reads Git blobs; it neither executes nor merges upstream implementations.
"""
from copy import deepcopy
from hashlib import sha256
import argparse
import ast
import importlib
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_INDEX = Path("biopipe/builtin_packages.json")
ROUTE_INDEX = Path("src/web/builtin_routes.json")


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else deepcopy(default)


def scan_sources(root=ROOT, sources=None):
    """Import fresh declarations, collect every error, and reject duplicate IDs."""
    from biopipe_sdk.protocol import validate_extension, describe_reader, describe_operator, PROTOCOL_VERSION, catalog_entry
    from src.task.step.base import Step
    from src.reader.base import Reader
    classes, errors, seen = [], [], set()
    for folder, base, kind in (("src/task/step/steps", Step, "operator"), ("src/reader/readers", Reader, "reader")):
        for path in sorted((root / folder).glob("*.py")):
            if path.name.startswith("_"):
                continue
            if sources is not None and path.relative_to(root).as_posix() not in sources:
                continue
            module_name = path.relative_to(root).with_suffix("").as_posix().replace("/", ".")
            try:
                module = importlib.reload(sys.modules[module_name]) if module_name in sys.modules else importlib.import_module(module_name)
                for cls in vars(module).values():
                    if not isinstance(cls, type) or not issubclass(cls, base) or cls is base or cls.__module__ != module_name:
                        continue
                    identifier = cls.name if kind == "operator" else getattr(cls, "name", None) or cls.__name__
                    if identifier in seen:
                        raise ValueError(f"Duplicate extension ID: {identifier}")
                    seen.add(identifier)
                    classes.append((kind, cls, path.relative_to(root).as_posix()))
            except Exception as exc:
                errors.append({"source": path.relative_to(root).as_posix(), "error": str(exc)})
    operators = {cls.name: cls for kind, cls, _ in classes if kind == "operator"}
    descriptors = []
    for kind, cls, source in classes:
        try:
            if kind == "operator":
                validate_extension(cls, kind)
                descriptor = describe_operator(cls)
            else:
                validate_extension(cls, kind)
                descriptor = describe_reader(cls())
            descriptors.append((descriptor, getattr(cls, "builtin_package", None), source))
        except Exception as exc:
            errors.append({"source": source, "error": str(exc)})
    return descriptors, errors


def package_manifest(descriptors, previous):
    from biopipe_sdk.protocol import PROTOCOL_VERSION
    owners = {(d["kind"], d["id"]): p["name"] for p in previous["packages"] for d in p["descriptors"]}
    packages = {p["name"]: {**deepcopy(p), "descriptors": []} for p in previous["packages"]}
    for descriptor, declared_owner, source in descriptors:
        key = (descriptor["kind"], descriptor["id"])
        name = declared_owner or owners.get(key) or ("biopipe-readers" if descriptor["kind"] == "reader" else "biopipe-core")
        if key in owners and name != owners[key]:
            raise ValueError(f"{source}: ownership of {descriptor['id']} cannot move from {owners[key]} to {name}")
        package = packages.setdefault(name, {"protocol_version": PROTOCOL_VERSION, "name": name, "title": name,
                                            "version": "1.0.0", "origin": "bundled", "descriptors": []})
        package["descriptors"].append(descriptor)
    from biopipe_sdk.protocol import PackageDescriptor
    for package in packages.values():
        package["protocol_version"] = PROTOCOL_VERSION
        package["descriptors"].sort(key=lambda d: (d["kind"], d["id"]))
        PackageDescriptor.model_validate(package)
    return {"protocol_version": PROTOCOL_VERSION, "packages": list(packages.values())}


def route_sources(root, route_roots=None):
    roots = [Path(p) for p in route_roots] if route_roots else [root / "routes"]
    paths = {}
    for directory in roots:
        directory = directory if directory.is_absolute() else root / directory
        if not directory.is_dir():
            raise ValueError(f"Route directory does not exist: {directory}")
        for path in sorted(set(directory.rglob("task.yaml")) | set(directory.rglob("task.yml"))):
            paths[path.resolve()] = path.parent.relative_to(directory).as_posix()
    return sorted(paths.items(), key=lambda pair: str(pair[0]))


def normalize_numbers(raw, catalog):
    """Normalize YAML 1.1 scientific notation only for declared numeric fields."""
    specs = {item["id"]: item for item in catalog["operators"]}
    for step in raw.get("steps", []):
        spec = specs.get(step.get("name"), {})
        for key, field in spec.get("parameters_schema", {}).get("properties", {}).items():
            params = step.get("params", {})
            value = params.get(key)
            if field.get("type") in ("number", "integer") and isinstance(value, str):
                number = float(value)
                params[key] = int(number) if field["type"] == "integer" and number.is_integer() else number


def build_routes(root, catalog, previous, route_roots=None):
    from src.web.graph import import_manifest
    from src.web.models import RouteDefinition
    from src.web.routes import prepare_interface, check_interface
    old = {r["id"]: r for r in previous.get("routes", [])}
    routes, sources, errors, ids, names = [], {}, [], set(), set()
    for path, relative in route_sources(root, route_roots):
        try:
            settings = read_json(path.with_name("route.json"), {})
            if settings.get("enabled", True) is False:
                continue
            key = settings.get("key", relative if relative != "." else path.parent.name)
            identifier = settings.get("id", "route_" + sha256(("biopipe/builtin/" + key).encode()).hexdigest()[:12])
            if identifier in ids:
                raise ValueError(f"Duplicate route ID: {identifier}")
            ids.add(identifier)
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Route YAML must be an object")
            normalize_numbers(raw, catalog)
            paths = [settings.get("base_dir", "."), *[s.get("path", "") for s in raw.get("sources", {}).values()]]
            if any(Path(p).is_absolute() or PureWindowsPath(p).is_absolute() for p in paths):
                raise ValueError("Bundled route paths must be relative so templates remain portable")
            name = settings.get("name", raw.get("name", key))
            if name in names:
                raise ValueError(f"Duplicate route name: {name}")
            names.add(name)
            graph = import_manifest(yaml.safe_dump(raw, allow_unicode=True), settings.get("base_dir", f".studio/builtin-inputs/{key}"), catalog, root)
            graph.name = name
            levels, rows = {}, {}
            for node in graph.nodes:
                parents = [edge.source for edge in graph.edges if edge.target == node.id]
                level = max((levels[parent] + 1 for parent in parents), default=0)
                levels[node.id] = level
                row = rows.get(level, 0)
                rows[level] = row + 1
                node.position.x, node.position.y = 70 + 290 * level, 100 + 210 * row
            graph = prepare_interface(graph, catalog, root)
            check_interface(graph, catalog)
            body = graph.model_dump(mode="json")
            before = old.get(identifier)
            version = (before["version"] + int(before["graph"] != body)) if before else 1
            record = {"id": identifier, "version": version, "name": name, "graph": body}
            RouteDefinition.model_validate(record)
            sources[identifier] = {"path": path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name,
                                   "sha256": sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()}
            if settings.get("source_commit"):
                sources[identifier]["commit"] = settings["source_commit"]
            routes.append(record)
        except Exception as exc:
            errors.append({"source": str(path), "error": str(exc)})
    return {"schema_version": 1, "sources": sources, "routes": sorted(routes, key=lambda r: r["id"])}, errors


def inventory(root=ROOT, source_ref=None, route_roots=None):
    """Static discovery works even if a newly added module cannot be imported."""
    known = read_json(root / PACKAGE_INDEX, {"packages": []})
    ids = {d["id"] for p in known["packages"] for d in p["descriptors"]}
    known_routes = {r["id"] for r in read_json(root / ROUTE_INDEX, {"routes": []})["routes"]}
    result = {"source_ref": source_ref, "extensions": [], "routes": [], "errors": []}
    route_keys = {}
    if source_ref:
        commit = subprocess.check_output(["git", "rev-parse", "--verify", "--end-of-options", source_ref + "^{commit}"], cwd=root, text=True).strip()
        paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit], cwd=root, text=True).splitlines()
        result["source_ref"] = commit
        selected = [p for p in paths if (p.startswith(("src/task/step/steps/", "src/reader/readers/")) and p.endswith(".py") and not Path(p).name.startswith("_"))
                    or (p.startswith(("routes/", "tasks/")) and Path(p).name in {"task.yaml", "task.yml"})]
        sources = [(p, subprocess.check_output(["git", "show", f"{commit}:{p}"], cwd=root).decode("utf-8")) for p in selected]
    else:
        paths = [*sorted((root / "src/task/step/steps").glob("[!_]*.py")), *sorted((root / "src/reader/readers").glob("[!_]*.py"))]
        found_routes = route_sources(root, route_roots)
        paths += [p for p, _ in found_routes]
        route_keys = {str(p): relative if relative != "." else p.parent.name for p, relative in found_routes}
        sources = [(p.relative_to(root).as_posix() if p.is_relative_to(root) else str(p), p.read_text(encoding="utf-8")) for p in paths]
    for path, text in sources:
        try:
            if path.endswith((".yaml", ".yml")):
                raw = yaml.safe_load(text)
                required = sorted({s["name"] for s in raw.get("steps", [])})
                settings = read_json((root / path).with_name("route.json"), {}) if not source_ref else {}
                default_key = Path(path).parent.name.removesuffix("_demo")
                if source_ref:
                    sidecar = Path(path).with_name("route.json").as_posix()
                    if sidecar in paths:
                        settings = json.loads(subprocess.check_output(["git", "show", f"{commit}:{sidecar}"], cwd=root).decode("utf-8"))
                    if path.startswith("routes/"):
                        default_key = Path(path).parent.relative_to("routes").as_posix()
                else:
                    default_key = route_keys.get(str((root / path).resolve()), default_key)
                key = settings.get("key", default_key)
                identifier = settings.get("id", "route_" + sha256(("biopipe/builtin/" + key).encode()).hexdigest()[:12])
                result["routes"].append({"source": path, "name": settings.get("name", raw.get("name", Path(path).parent.name)),
                                         "indexed": identifier in known_routes,
                                         "operators": required, "missing_operators": sorted(set(required) - ids)})
                continue
            for cls in [n for n in ast.parse(text).body if isinstance(n, ast.ClassDef)]:
                bases = {ast.unparse(base).split(".")[-1] for base in cls.bases}
                if not bases & {"Step", "Operator", "Reader"}:
                    continue
                attributes = {}
                for assignment in cls.body:
                    if isinstance(assignment, (ast.Assign, ast.AnnAssign)):
                        for target in assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]:
                            if isinstance(target, ast.Name):
                                try:
                                    attributes[target.id] = ast.literal_eval(assignment.value)
                                except (ValueError, TypeError):
                                    pass
                identifier = attributes.get("name", cls.name)
                result["extensions"].append({"id": identifier, "source": path, "kind": "reader" if "Reader" in bases else "operator",
                                             "indexed": identifier in ids, "local_source": (root / path).is_file(),
                                             "source_differs": source_ref is not None and (root / path).is_file()
                                             and (root / path).read_text(encoding="utf-8") != text.replace("\r\n", "\n")})
        except Exception as exc:
            result["errors"].append({"source": path, "error": str(exc)})
    return result


def maintain(action="check", *, root=ROOT, route_roots=None, output_dir=None, scope="all"):
    from biopipe_sdk.protocol import PROTOCOL_VERSION, catalog_entry
    root = Path(root).resolve()
    previous = read_json(root / PACKAGE_INDEX, {"protocol_version": PROTOCOL_VERSION, "packages": []})
    descriptors, errors = scan_sources(root)
    candidate = package_manifest(descriptors, previous)
    catalog = {"schema_version": 1, "protocol_version": PROTOCOL_VERSION, "contract_version": 1,
               "operators": [catalog_entry(d) for d, _, _ in descriptors if d["kind"] == "operator"],
               "readers": [catalog_entry(d) for d, _, _ in descriptors if d["kind"] == "reader"]}
    outputs = {}
    if scope != "routes":
        outputs[PACKAGE_INDEX] = candidate
    if scope != "packages":
        routes, route_errors = build_routes(root, catalog, read_json(root / ROUTE_INDEX, {}), route_roots)
        errors += route_errors
        outputs[ROUTE_INDEX] = routes
    destination = Path(output_dir).resolve() if output_dir else root
    changed = [path.as_posix() for path, data in outputs.items() if read_json(destination / path, None) != data]
    report = {"action": action, "operators": len(catalog["operators"]), "readers": len(catalog["readers"]),
              "packages": len(candidate["packages"]), "routes": len(outputs.get(ROUTE_INDEX, {}).get("routes", [])),
              "changed": changed, "errors": errors, "written": []}
    if errors:
        return report
    if action == "build":
        from src.web.storage import FileLock, atomic_json
        with FileLock(destination / ".registry-maintenance.lock"):
            for path, data in outputs.items():
                if path.as_posix() in changed:
                    atomic_json(destination / path, data)
                    report["written"].append(str(destination / path))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["discover", "check", "build"])
    parser.add_argument("--source-ref", help="Static discovery against a locally fetched Git ref (discover only)")
    parser.add_argument("--route-root", action="append", help="Repeatable directory containing task.yaml/task.yml; defaults to routes/")
    parser.add_argument("--output-dir", type=Path, help="Write/check generated indexes under an alternate directory")
    parser.add_argument("--scope", choices=["all", "packages", "routes"], default="all")
    args = parser.parse_args(argv)
    if args.source_ref and args.action != "discover":
        parser.error("--source-ref is for discovery only; adapt reviewed code locally before building")
    os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
    try:
        result = inventory(source_ref=args.source_ref, route_roots=args.route_root) if args.action == "discover" else maintain(
            args.action, route_roots=args.route_root, output_dir=args.output_dir, scope=args.scope)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return int(bool(result["errors"]) or (args.action == "check" and bool(result["changed"])))
    except Exception as exc:
        print(json.dumps({"errors": [{"error": str(exc)}]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
