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


@lru_cache(maxsize=1)
def bundled_manifest():
    return json.loads(Path(__file__).with_name("builtin_packages.json").read_text(encoding="utf-8"))


def bundled_entries(kind):
    for package in bundled_manifest()["packages"]:
        for descriptor in package["descriptors"]:
            if descriptor["kind"] == kind:
                yield package, descriptor


def load_entry(descriptor):
    module, name = descriptor["entry_point"].split(":", 1)
    cls = getattr(importlib.import_module(module), name)
    # Legacy Python/YAML callers keep their historical parameter semantics.
    cls.parameters_schema = deepcopy(descriptor["parameters_schema"])
    cls.legacy_parameters = bool(descriptor.get("legacy_parameters", True))
    cls._package_descriptor = deepcopy(descriptor)
    return cls


@lru_cache(maxsize=1)
def bundled_state():
    packages, descriptors = [], []
    for original in bundled_manifest()["packages"]:
        package = {k: deepcopy(v) for k, v in original.items() if k != "descriptors"}
        # Include implementation bytes: editing a builtin never silently reuses a lock.
        digest = hashlib.sha256(json.dumps(original, sort_keys=True).encode())
        root = Path(__file__).resolve().parents[1]
        paths = {root / (d["entry_point"].split(":")[0].replace(".", "/") + ".py") for d in original["descriptors"]}
        paths.update((root / "src/task/step/steps").glob("_*.py"))
        paths.update((root / "src/reader/readers").glob("_*.py"))
        for path in sorted(paths):
            digest.update(path.relative_to(root).as_posix().encode())
            # Normalize universal newlines so Git's CRLF/LF checkout policy
            # does not make identical providers look different across machines.
            digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
        package.update(sha256=digest.hexdigest(), enabled=True)
        packages.append(package)
        for original_descriptor in original["descriptors"]:
            descriptor = deepcopy(original_descriptor)
            descriptor.update(distribution=package["name"], package_version=package["version"], origin="bundled",
                              implementation={k: package[k] for k in ("version", "sha256")})
            descriptor["implementation"]["package"] = package["name"]
            descriptors.append(descriptor)
    return {"packages": packages, "descriptors": descriptors}


def owns_legacy_id(package, identifier):
    return any(p["name"] == package and d["id"] == identifier
               for p in bundled_manifest()["packages"] for d in p["descriptors"])
