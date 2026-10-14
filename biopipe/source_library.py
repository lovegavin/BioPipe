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

from biopipe.plugins import ROOT, run_process

SOURCE_DIRS = {"operator": "src/task/step/steps", "reader": "src/reader/readers"}


def directories(root=ROOT):
    if root is None:
        return {}
    return {kind: root / relative for kind, relative in SOURCE_DIRS.items()}


def describe(root, output):
    """Child process only: replace source-module search paths before discovery."""
    os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
    for relative in SOURCE_DIRS.values():
        package = importlib.import_module(relative.replace("/", "."))
        package.__path__ = [str(root / relative)]
    from src.task import operator_catalog
    operator_catalog.__file__ = str(root / "src/task/operator_catalog.py")
    from biopipe.registry import scan_sources, package_manifest, PACKAGE_INDEX, read_json
    descriptors, errors = scan_sources(root)
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
        init.extend([f"{alias} = getattr(import_module({source_module!r}), {clsname!r})",
                     f"{alias}.parameters_schema = _definitions[{index}]['parameters_schema']",
                     f"{alias}.legacy_parameters = _definitions[{index}].get('legacy_parameters', True)",
                     f"{alias}._package_descriptor = _definitions[{index}]"])
        groups[descriptor["kind"]].append(f"{alias} = {module}:{alias}")
    files[f"{module}/__init__.py"] = ("\n".join(init) + "\n").encode()
    files[f"{module}/definitions.json"] = json.dumps(definitions, ensure_ascii=False, sort_keys=True).encode()
    info = f"{name.replace('-', '_').replace('.', '_')}-{version}.dist-info"
    entries = []
    for kind, group in (("operator", "operators"), ("reader", "readers")):
        if groups[kind]:
            entries.extend([f"[biopipe.{group}]", *groups[kind], ""])
    files[f"{info}/entry_points.txt"] = "\n".join(entries).encode()
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
    environment = dict(os.environ, BIOPIPE_REGISTRY_MAINTENANCE="1")
    run_process([manager.python_for(current), "-m", "biopipe.source_library", staged, output], env=environment)
    manifest = json.loads(output.read_text(encoding="utf-8"))
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
    if len(sys.argv) != 3:
        raise SystemExit("Use: python -m biopipe.source_library <snapshot-root> <output.json>")
    describe(Path(sys.argv[1]), Path(sys.argv[2]))
