"""Helpers for the shipped large-resource manifest (``biopipe/resources.json``).

The manifest is the single place that records, for every large external
resource (model weights, database bundles, official checkouts), the environment
variable that can point at a local copy, the default roots to probe, and the
exact files a dependent operator needs.  ``resource_preflight`` and the
``scripts/check_resources.py`` helper both build on this module, so an operator
fails with an actionable installation command instead of a bare
``FileNotFoundError``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.errors import StepError

MANIFEST_NAME = "resources.json"


@dataclass(frozen=True)
class Resource:
    """One entry of ``biopipe/resources.json``."""

    id: str
    title: str
    kind: str
    url: str
    install: str
    env: str
    roots: tuple[str, ...]
    files: tuple[str, ...]

    @classmethod
    def from_entry(cls, entry: dict[str, Any]) -> "Resource":
        identifier = str(entry.get("id") or "").strip()
        if not identifier:
            raise StepError("resource manifest entry without an id")
        files = tuple(str(name) for name in entry.get("files") or [] if str(name).strip())
        if not files:
            raise StepError(f"resource '{identifier}' lists no expected files")
        roots = tuple(str(root) for root in entry.get("roots") or [] if str(root).strip())
        return cls(
            id=identifier,
            title=str(entry.get("title") or identifier),
            kind=str(entry.get("kind") or "resource"),
            url=str(entry.get("url") or ""),
            install=str(entry.get("install") or ""),
            env=str(entry.get("env") or ""),
            roots=roots,
            files=files,
        )


def manifest_path() -> Path:
    """Locate ``biopipe/resources.json`` in a source tree or an installed wheel."""

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "biopipe" / MANIFEST_NAME
        if candidate.is_file():
            return candidate
    try:  # installed package: biopipe/resources.json sits next to the package
        from importlib.resources import files

        candidate = Path(str(files("biopipe").joinpath(MANIFEST_NAME)))
        if candidate.is_file():
            return candidate
    except Exception:  # pragma: no cover - defensive, importlib.resources missing
        pass
    raise StepError(
        "biopipe/resources.json is missing from this installation; "
        "reinstall the package or run from the repository root"
    )


def load_resources(path: Path | str | None = None) -> dict[str, Resource]:
    """Read the manifest and return its entries keyed by resource id."""

    file = Path(path) if path is not None else manifest_path()
    if not file.is_file():
        raise StepError(f"resource manifest {file} does not exist")
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StepError(f"resource manifest {file} is not valid JSON: {exc}") from exc
    entries = payload.get("resources") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise StepError(f"resource manifest {file} has no 'resources' list")
    resources: dict[str, Resource] = {}
    for entry in entries:
        resource = Resource.from_entry(entry)
        if resource.id in resources:
            raise StepError(f"resource manifest lists '{resource.id}' twice")
        resources[resource.id] = resource
    return resources


def resolve_root(resource: Resource, root: str | Path | None = None) -> Path | None:
    """First existing directory among explicit root, env override and defaults."""

    if root:
        path = Path(str(root)).expanduser()
        return path if path.is_dir() else None
    if resource.env and os.environ.get(resource.env):
        path = Path(str(os.environ[resource.env])).expanduser()
        return path if path.is_dir() else None
    for candidate in resource.roots:
        path = Path(candidate).expanduser()
        if path.is_dir():
            return path
    return None


def check_resource(resource: Resource, root: str | Path | None = None) -> dict[str, Any]:
    """Presence and size of every expected file of one resource."""

    resolved = resolve_root(resource, root)
    files: dict[str, dict[str, Any]] = {}
    for name in resource.files:
        path = resolved / name if resolved is not None else None
        present = bool(path is not None and path.is_file())
        files[name] = {
            "present": present,
            "size_mb": round(path.stat().st_size / (1024 * 1024), 3) if present and path is not None else 0.0,
        }
    missing = [name for name, info in files.items() if not info["present"]]
    if resolved is None:
        status = "missing"
    elif missing:
        status = "partial"
    else:
        status = "ok"
    return {
        "id": resource.id,
        "title": resource.title,
        "kind": resource.kind,
        "status": status,
        "root": str(resolved) if resolved is not None else "",
        "env": resource.env,
        "url": resource.url,
        "install": resource.install,
        "files": files,
        "missing": missing,
        "size_mb": round(sum(info["size_mb"] for info in files.values()), 3),
    }


def check_many(ids: list[str] | None = None, root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Check every selected resource id (all of them when ``ids`` is empty)."""

    resources = load_resources()
    if ids:
        unknown = [identifier for identifier in ids if identifier not in resources]
        if unknown:
            raise StepError(
                f"unknown resource(s): {', '.join(unknown)}; "
                f"known resources: {', '.join(sorted(resources))}"
            )
        selected = [resources[identifier] for identifier in ids]
    else:
        selected = [resources[identifier] for identifier in sorted(resources)]
    return {resource.id: check_resource(resource, root) for resource in selected}


def remedy(check: dict[str, Any]) -> str:
    """One-line, copy-paste friendly explanation for a failed check."""

    parts = [f"resource '{check['id']}' is {check['status']}"]
    if check["root"]:
        parts.append(f"under {check['root']}")
        if check["missing"]:
            parts.append(f"missing: {', '.join(check['missing'])}")
    else:
        parts.append("no candidate directory exists")
    if check["env"]:
        parts.append(f"set {check['env']} to the directory that holds these files")
    if check["install"]:
        parts.append(f"install: {check['install']}")
    if check["url"]:
        parts.append(check["url"])
    return "; ".join(parts)


def require(operator: str, resource_id: str, root: str | Path | None = None) -> tuple[Resource, Path]:
    """Return the resource and its root directory, or raise a StepError."""

    resources = load_resources()
    resource = resources.get(resource_id)
    if resource is None:
        raise StepError(
            f"{operator}: unknown resource '{resource_id}'; "
            f"known resources: {', '.join(sorted(resources))}"
        )
    check = check_resource(resource, root)
    if check["status"] != "ok":
        raise StepError(f"{operator}: {remedy(check)}")
    assert check["root"]
    return resource, Path(check["root"])
