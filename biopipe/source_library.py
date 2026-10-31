"""Refresh the existing operator/Reader source library in an isolated process.

Source files are the authoring interface. Immutable provider wheels are an
internal implementation detail, sharing the existing package/runtime protocol.
"""
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

from biopipe.plugins import ROOT

SOURCE_DIRS = {"operator": "src/task/step/steps", "reader": "src/reader/readers"}


def directories(root=ROOT):
    if root is None:
        return {}
    return {kind: root / relative for kind, relative in SOURCE_DIRS.items()}


def describe(root, output, sources=None):
    """Child process only: replace source-module search paths before discovery."""
    os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
    for relative in SOURCE_DIRS.values():
        package = importlib.import_module(relative.replace("/", "."))
        package.__path__ = [str(root / relative)]
    from src.task import operator_catalog
    operator_catalog.__file__ = str(root / "src/task/operator_catalog.py")
    from biopipe.registry import scan_sources, package_manifest, PACKAGE_INDEX, read_json
    descriptors, errors = scan_sources(root, sources, normalize_categories=False)
    if sources is not None:
        output.write_text(json.dumps({'descriptors': descriptors, 'errors': errors}, ensure_ascii=False), encoding='utf-8')
        return
    if errors:
        raise ValueError("\n".join(f"{e['source']}: {e['error']}" for e in errors))
    manifest = package_manifest(descriptors, read_json(root / PACKAGE_INDEX, {"packages": []}))
    output.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def provider_wheel(package, root, output):
    from biopipe.dropins import write_wheel
    from packaging.version import Version
    name, version = package["name"], str(Version(package["version"]))
    module = "biopipe_library_" + name.replace("-", "_").replace(".", "_")
    prefixes = {SOURCE_DIRS["operator"].replace("/", "."): module + ".steps",
                SOURCE_DIRS["reader"].replace("/", "."): module + ".readers"}
    def rewrite(value):
        for before, after in prefixes.items():
            value = value.replace(before, after)
        return value
    files = {}
    # Copy the small module trees, preserving helper/cross-operator imports in a
    # private namespace. No new source can overwrite the engine's src package.
    for kind, relative in SOURCE_DIRS.items():
        folder = "steps" if kind == "operator" else "readers"
        for source in sorted((root / relative).rglob("*")):
            if source.is_file():
                path = source.relative_to(root / relative).as_posix()
                files[f"{module}/{folder}/{path}"] = (rewrite(source.read_text(encoding="utf-8")).encode("utf-8")
                    if source.suffix == ".py" else source.read_bytes())
    definitions = deepcopy(package["descriptors"])
    init = ["import json", "from pathlib import Path", "from importlib import import_module",
            "_definitions = json.loads(Path(__file__).with_name('definitions.json').read_text(encoding='utf-8'))"]
    groups = {"operator": [], "reader": []}
    for index, descriptor in enumerate(definitions):
        descriptor["entry_point"] = rewrite(descriptor["entry_point"])
        descriptor["module"] = descriptor["entry_point"].split(":")[0]
        source_module, clsname = descriptor["entry_point"].split(":")
        alias = f"Entry{index}"
        # __getattr__ resolves only the selected entry.
        groups[descriptor["kind"]].append(f"{alias} = {module}:{alias}")
    init.extend(["def __getattr__(name):", "    index = int(name[5:]) if name.startswith('Entry') and name[5:].isdigit() else -1",
                 "    if index < 0 or index >= len(_definitions): raise AttributeError(name)",
                 "    d = _definitions[index]", "    module, clsname = d['entry_point'].split(':')",
                 "    cls = getattr(import_module(module), clsname)",
                 "    cls.parameters_schema = d['parameters_schema']", "    cls.legacy_parameters = d.get('legacy_parameters', True)",
                 "    cls._package_descriptor = d", "    return cls"])
    files[f"{module}/__init__.py"] = ("\n".join(init) + "\n").encode()
    files[f"{module}/definitions.json"] = json.dumps(definitions, ensure_ascii=False, sort_keys=True).encode()
    info = f"{name.replace('-', '_').replace('.', '_')}-{version}.dist-info"
    entries = []
    for kind, group in (("operator", "operators"), ("reader", "readers")):
        if groups[kind]:
            entries.extend([f"[biopipe.{group}]", *groups[kind], ""])
    files[f"{info}/entry_points.txt"] = "\n".join(entries).encode()
    # Requirements belong to each descriptor; a package may contain conflicts.
    files[f"{info}/biopipe.json"] = json.dumps({"protocol_version": 1, "name": name, "version": version,
        "descriptors": definitions}).encode()
    return write_wheel(files, name, version, [], output)


def prepare(manager, current, temporary):
    """Capture exact bytes before scanning; no source tree or shipped index edits."""
    from biopipe.dropins import snapshot
    root = manager.source_root
    if root is None:
        return {"wheels": [], "updated": [], "unchanged": [], "receipt": current.get("source_library")}
    staged = temporary / "source"
    digest = hashlib.sha256()
    for relative in [*SOURCE_DIRS.values(), "src/task/operator_ui.json", "biopipe/builtin_packages.json"]:
        source = root / relative
        target = staged / relative if source.is_dir() else (staged / relative).parent
        digest.update(relative.encode() + snapshot(source, target).encode())
    fingerprint = digest.hexdigest()
    previous = current.get("source_library", {})
    if previous.get("sha256") == fingerprint:
        return {"wheels": [], "updated": [], "unchanged": ["operator / Reader source directories"], "receipt": previous}
    output = temporary / "manifest.json"
    # Scan in the shared runtime first. Only modules that actually need an
    # unavailable/conflicting import are retried in a prepared dependency target.
    # Optional lazy imports do not prevent unrelated operators from registering.
    from biopipe_sdk.dependencies import source_requirements
    from biopipe.targets import TargetBuilder, invoke, paths_for
    from biopipe.registry import package_manifest, read_json, PACKAGE_INDEX
    builder = TargetBuilder(manager, current)
    source_paths = [p.relative_to(staged).as_posix() for relative in SOURCE_DIRS.values()
                    for p in sorted((staged / relative).glob('*.py')) if not p.name.startswith('_')]
    selected = temporary / 'sources.json'
    selected.write_text(json.dumps(source_paths), encoding='utf-8')
    invoke(paths_for({**current, '_runtime_root': str(manager.directory.resolve())}),
           'biopipe.source_library', [staged, output, selected], temporary)
    scan = json.loads(output.read_text(encoding='utf-8'))
    records = scan['descriptors']
    for failure in scan['errors']:
        source = failure['source']
        try:
            declared = source_requirements((staged / source).read_bytes())
            if not declared:
                raise ValueError(failure['error'])
            execution = builder.prepare(declared)
            paths = execution.get('paths', []) if execution['mode'] == 'isolated' else builder.shared
            selected.write_text(json.dumps([source]), encoding='utf-8')
            invoke([manager.directory / p for p in paths], 'biopipe.source_library', [staged, output, selected], temporary)
            retry = json.loads(output.read_text(encoding='utf-8'))
            if retry['errors']:
                raise ValueError(retry['errors'][0]['error'])
            records.extend(retry['descriptors'])
        except Exception as exc:
            raise ValueError(f'{source}: {exc}') from exc
    ids = [r[0]['id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate extension ID in source library')
    manifest = package_manifest(records, read_json(staged / PACKAGE_INDEX, {'packages': []}))
    installed = {p["name"]: p for p in current["packages"]}
    source_managed = set(previous.get("packages", []))
    seen = set(current.get("bundled_seen", []))
    packages = [p for p in manifest["packages"] if p["descriptors"] and
                (installed.get(p["name"], {}).get("origin") == "bundled" or
                 (p["name"] in source_managed and p["name"] in installed) or
                 p["name"] not in installed and p["name"] not in seen)]
    wheels = [provider_wheel(p, staged, temporary / "wheels") for p in packages]
    return {"wheels": wheels, "updated": [p["name"] for p in packages], "unchanged": [],
            "receipt": {"sha256": fingerprint, "packages": [p["name"] for p in packages]}}


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Use: python -m biopipe.source_library <snapshot-root> <output.json>")
    describe(Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) == 4 else None)
