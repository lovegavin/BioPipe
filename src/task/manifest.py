# src/task/manifest.py
"""Task manifest: load and validate task.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.core import ManifestError


_SOURCE_KEYS = {"path", "dims", "labels", "args"}
_STEP_KEYS = {"name", "inputs", "params"}


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise ManifestError(f"Missing manifest: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ManifestError("Manifest must be a YAML mapping")

    for section in ("sources", "steps"):
        if section not in raw:
            raise ManifestError(f"Manifest missing '{section}' section")

    _validate_sources(raw["sources"])
    _validate_steps(raw["steps"])
    return raw


def _validate_sources(sources: dict) -> None:
    for name, spec in sources.items():
        if not isinstance(spec, dict):
            raise ManifestError(f"Source '{name}' must be a mapping")

        # path and dims are required; labels is optional.
        for key in ("path", "dims"):
            if key not in spec:
                raise ManifestError(
                    f"Source '{name}' missing required field '{key}'"
                )

        unknown = set(spec) - _SOURCE_KEYS
        if unknown:
            raise ManifestError(
                f"Source '{name}' has unknown keys: {sorted(unknown)}. "
                f"Allowed: {sorted(_SOURCE_KEYS)}"
            )

        if not isinstance(spec["dims"], list):
            raise ManifestError(
                f"Source '{name}': dims must be a list of names"
            )

        labels = spec.get("labels")
        if labels is not None and not isinstance(labels, dict):
            raise ManifestError(
                f"Source '{name}': labels must be a mapping when present"
            )

        args = spec.get("args")
        if args is not None and not isinstance(args, dict):
            raise ManifestError(f"Source '{name}': args must be a mapping")


def _validate_steps(steps: list) -> None:
    for i, spec in enumerate(steps):
        if not isinstance(spec, dict):
            raise ManifestError(f"Step {i} must be a mapping")

        if "name" not in spec:
            raise ManifestError(f"Step {i} missing 'name'")

        unknown = set(spec) - _STEP_KEYS
        if unknown:
            raise ManifestError(
                f"Step {i} ('{spec['name']}') unknown keys: "
                f"{sorted(unknown)}. Allowed: {sorted(_STEP_KEYS)}"
            )

        inputs = spec.get("inputs", [])
        if not isinstance(inputs, list):
            raise ManifestError(
                f"Step {i} ('{spec['name']}'): inputs must be a list"
            )

        params = spec.get("params")
        if params is not None and not isinstance(params, dict):
            raise ManifestError(
                f"Step {i} ('{spec['name']}'): params must be a mapping"
            )