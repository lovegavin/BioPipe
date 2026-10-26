"""Concrete task values, independent of mutable operator parameter schemas."""
from copy import deepcopy
import json
from pathlib import Path


def read_values(directory, reference):
    """Read a contained relative JSON sidecar; never fall back to defaults."""
    if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
        raise ValueError("parameters_file must be a relative JSON path")
    root = Path(directory).resolve()
    path = (root / reference).resolve()
    if not path.is_relative_to(root) or path.suffix != ".json":
        raise ValueError("parameters_file must stay inside the workflow directory")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        json.dumps(value, allow_nan=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read parameter values: {reference}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Parameter values must be a JSON object")
    return value


def split_task(manifest):
    """Return topology and a complete value snapshot for one execution."""
    task = deepcopy(manifest)
    values = {"format": "biopipe.task-parameters", "schema_version": 1,
              "params": task.pop("params", {}), "sources": {}, "steps": []}
    for name, source in task["sources"].items():
        values["sources"][name] = source.pop("args", {})
    for step in task["steps"]:
        values["steps"].append({"name": step["name"], "inputs": deepcopy(step["inputs"]),
                                "params": step.pop("params", {}),
                                "context_params": step.pop("context_params", {})})
    task["parameters_file"] = "parameters.json"
    return task, values


def restore_task(manifest, values):
    """Reject mismatched pairs rather than mixing snapshots with live defaults."""
    def invalid():
        raise ValueError("Task parameter values do not match task.yaml")

    if (not isinstance(values, dict) or set(values) != {"format", "schema_version", "params", "sources", "steps"}
            or values["format"] != "biopipe.task-parameters" or values["schema_version"] != 1
            or not isinstance(values["params"], dict) or not isinstance(values["sources"], dict)
            or not isinstance(values["steps"], list)
            or set(values["sources"]) != set(manifest.get("sources", {}))
            or len(values["steps"]) != len(manifest.get("steps", []))):
        invalid()
    result = deepcopy(manifest)
    if result.get("params"):
        invalid()
    result.pop("parameters_file", None)
    result["params"] = deepcopy(values["params"])
    for name, source in result["sources"].items():
        if source.get("args") or not isinstance(values["sources"][name], dict):
            invalid()
        source["args"] = deepcopy(values["sources"][name])
    for step, entry in zip(result["steps"], values["steps"]):
        if (not isinstance(entry, dict) or set(entry) != {"name", "inputs", "params", "context_params"}
                or entry["name"] != step.get("name") or entry["inputs"] != step.get("inputs")
                or step.get("params") or step.get("context_params")
                or not isinstance(entry["params"], dict) or not isinstance(entry["context_params"], dict)):
            invalid()
        step["params"] = deepcopy(entry["params"])
        if entry["context_params"]:
            step["context_params"] = deepcopy(entry["context_params"])
    return result
