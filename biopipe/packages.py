"""Bundled providers use the same descriptors and ownership as installed wheels.

The checked-in manifest is the startup index; scanning is a maintenance operation.
This module deliberately imports no engine modules at module load time.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path


def _stamp(path):
    stat = path.stat()
    return str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size


@lru_cache(maxsize=1)
def _manifest(stamp):
    return json.loads(Path(stamp[0]).read_text(encoding="utf-8"))


def bundled_manifest():
    return _manifest(_stamp(Path(__file__).with_name("builtin_packages.json")))


def _provider_paths(root, package):
    paths = {root / (d["entry_point"].split(":")[0].replace(".", "/") + ".py") for d in package["descriptors"]}
    paths.update((root / "src/task/step/steps").glob("_*.py"))
    paths.update((root / "src/reader/readers").glob("_*.py"))
    return sorted(paths)


def bundled_entries(kind):
    for package in bundled_manifest()["packages"]:
        for descriptor in package["descriptors"]:
            if descriptor["kind"] == kind:
                yield package, descriptor


def load_entry(descriptor):
    from biopipe_sdk.declarations import load_class
    return load_class(descriptor)


def bundled_state(root=None, *, manifest_only=False):
    """Read compiled descriptors, optionally trusting only their manifest identity.

    Persistent servers opt into metadata-only reads. Their package digest covers
    the manifest (including its code_sha values); implementation bytes remain
    validated by the runtime loader before execution. Desktop callers retain
    source-change detection until an explicit refresh rebuilds the descriptors.
    """
    root = Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
    index = _stamp(root / "biopipe/builtin_packages.json")
    if manifest_only:
        return _bundled_state(index, (), manifest_only=True)
    # A long-lived desktop must notice source edits before its next worker starts.
    paths = {p for package in _manifest(index)["packages"] for p in _provider_paths(root, package)}
    return _bundled_state(index, tuple(_stamp(p) for p in sorted(paths)))


@lru_cache(maxsize=1)
def _bundled_state(index, sources, manifest_only=False):
    root = Path(index[0]).parents[1]
    packages, descriptors = [], []
    for original in _manifest(index)["packages"]:
        package = {k: deepcopy(v) for k, v in original.items() if k != "descriptors"}
        # The manifest already carries the runtime's pinned code identities.
        digest = hashlib.sha256(json.dumps(original, sort_keys=True).encode())
        # Default mode also detects source edits before registry maintenance.
        for path in (() if manifest_only else _provider_paths(root, original)):
            digest.update(path.relative_to(root).as_posix().encode())
            # Normalize universal newlines so Git's CRLF/LF checkout policy
            # does not make identical providers look different across machines.
            digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
        package.update(sha256=digest.hexdigest(), enabled=True, code_sha=original["descriptors"][0]["code_sha"])
        if manifest_only:
            package["manifest_only"] = True
        packages.append(package)
        for original_descriptor in original["descriptors"]:
            descriptor = deepcopy(original_descriptor)
            descriptor.update(distribution=package["name"], package_version=package["version"], origin="bundled",
                              implementation={k: package[k] for k in ("version", "sha256")})
            descriptor["implementation"].update(package=package["name"], code_sha=descriptor["code_sha"], declaration_sha=descriptor["declaration_sha"])
            descriptors.append(descriptor)
    return {"packages": packages, "descriptors": descriptors}


def owns_builtin_id(package, identifier):
    return any(p["name"] == package and d["id"] == identifier
               for p in bundled_manifest()["packages"] for d in p["descriptors"])
