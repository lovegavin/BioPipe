# src/task/manifest.py
"""Task manifest: load and validate task.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.core import ManifestError


_SOURCE_KEYS = {"path", "dims", "labels", "args"}
_STEP_KEYS = {"name", "inputs", "params"}
_LABEL_STRINGS = {"builtin", "auto"}


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

        if not isinstance(spec["dims"], list) or not spec["dims"]:
            raise ManifestError(
                f"Source '{name}': dims must be a non-empty list"
            )

        labels = spec.get("labels", {})
        if not isinstance(labels, dict):
            raise ManifestError(
                f"Source '{name}': labels must be a mapping"
            )

        dim_set = set(spec["dims"])
        for dim_name, rule in labels.items():
            if dim_name not in dim_set:
                raise ManifestError(
                    f"Source '{name}': labels has entry for unknown "
                    f"dim '{dim_name}'. Known: {sorted(dim_set)}"
                )
            _validate_label_rule(name, dim_name, rule, dim_set)

        args = spec.get("args")
        if args is not None and not isinstance(args, dict):
            raise ManifestError(f"Source '{name}': args must be a mapping")


def _validate_label_rule(source: str, dim: str, rule, dim_set: set) -> None:
    if rule is None:
        return
    if isinstance(rule, str):
        if rule not in _LABEL_STRINGS:
            raise ManifestError(
                f"Source '{source}': labels.{dim} string must be one "
                f"of {sorted(_LABEL_STRINGS)}, got {rule!r}"
            )
        return
    if isinstance(rule, dict):
        for k, v in rule.items():
            if not isinstance(k, str):
                raise ManifestError(
                    f"Source '{source}': labels.{dim} keys must be "
                    f"strings, got {k!r}"
                )
            if not isinstance(v, int):
                raise ManifestError(
                    f"Source '{source}': labels.{dim}.{k} must be an "
                    f"int, got {v!r}"
                )
        return
    raise ManifestError(
        f"Source '{source}': labels.{dim} must be 'builtin', 'auto', "
        f"a mapping, or omitted; got {type(rule).__name__}"
    )


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