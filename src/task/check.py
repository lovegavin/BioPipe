"""Static task validation without executing any operator or reader."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from biopipe_sdk.protocol import validate_parameters
from src.reader import pick_reader


def check_manifest(task_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate paths, Reader options, step params, inputs and outputs.

    This deliberately does not read data or run operators. It is the
    pre-flight check an LLM must pass before a user imports/runs a task.
    """
    from src.task import STEPS

    task_dir = Path(task_dir).resolve()
    errors: list[dict[str, str]] = []
    sources: dict[str, dict[str, Any]] = {}
    available: set[str] = set()

    raw_sources = manifest.get("sources") or {}
    if not isinstance(raw_sources, dict) or not raw_sources:
        errors.append({"where": "sources", "message": "task.yaml needs a non-empty sources mapping"})
        raw_sources = {}

    for name, spec in raw_sources.items():
        if not isinstance(spec, dict) or not spec.get("path"):
            errors.append({"where": f"source:{name}", "message": "source needs a path"})
            continue
        path = (task_dir / spec["path"]).resolve()
        if not path.is_file():
            errors.append({"where": f"source:{name}", "message": f"file not found: {path}"})
            continue
        args = dict(spec.get("args") or {})
        reader_name = args.pop("reader", None)
        try:
            reader = pick_reader(path, name=reader_name)
            if reader.parameters_schema is not None:
                validate_parameters(reader.parameters_schema, args)
        except Exception as exc:
            errors.append({"where": f"source:{name}", "message": f"Reader error: {exc}"})
            continue
        dims = spec.get("dims")
        if not isinstance(dims, list) or not dims:
            errors.append({"where": f"source:{name}", "message": "source needs a non-empty dims list"})
        available.add(name)
        sources[name] = {
            "path": str(path),
            "reader": type(reader).__name__,
            "dims": dims,
            "exists": True,
        }

    raw_steps = manifest.get("steps") or []
    if not isinstance(raw_steps, list) or not raw_steps:
        errors.append({"where": "steps", "message": "task.yaml needs a non-empty steps list"})
        raw_steps = []

    step_reports = []
    for index, spec in enumerate(raw_steps, start=1):
        where = f"step:{index}"
        if not isinstance(spec, dict) or not spec.get("name"):
            errors.append({"where": where, "message": "step needs a name"})
            continue
        name = spec["name"]
        cls = STEPS.get(name)
        if cls is None:
            errors.append({"where": where, "message": f"unknown operator: {name}"})
            continue
        inputs = list(spec.get("inputs") or [])
        for ref in inputs:
            if ref not in available:
                errors.append({"where": where, "message": f"input {ref!r} is not produced before this step"})
        arity = cls.inputs_arity
        if arity != "*" and len(inputs) != arity:
            errors.append({"where": where, "message": f"{name} expects {arity} inputs, got {len(inputs)}"})
        params = dict(spec.get("params") or {})
        params.pop("_input_names", None)
        output = params.pop(cls.output_parameter, None) if cls.output_parameter else None
        if cls.parameters_schema is not None:
            try:
                validate_parameters(cls.parameters_schema, params)
            except Exception as exc:
                errors.append({"where": where, "message": f"{name} params: {exc}"})
                continue
        filename = params.get("filename")
        if filename is not None and (
            not isinstance(filename, str)
            or Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
            or ":" in filename
        ):
            errors.append({"where": where, "message": "filename must not contain a directory or drive"})
        produced = []
        if cls.output_parameter:
            produced.append(str(output or cls.name))
        else:
            produced.extend(cls.outputs)
        for out in produced:
            if out in available:
                errors.append({"where": where, "message": f"output {out!r} is defined more than once"})
            available.add(out)
        step_reports.append({"index": index, "name": name, "inputs": inputs, "outputs": produced})

    return {
        "ok": not errors,
        "task_dir": str(task_dir),
        "sources": sources,
        "steps": step_reports,
        "errors": errors,
    }
