"""Report whether the large resources of ``src/task/step/steps/resources.json`` are installed."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._resources_common import (
    check_many,
    load_resources,
    manifest_path,
    remedy,
)

_STATISTICS = ("present", "size_mb")


class ResourcePreflightStep(Step):
    """Check the files of one or all large resources and report remedies."""

    provider = "operon-core"

    parameters_file = "resource_preflight.ResourcePreflightStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "resource_preflight",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Large-resource preflight",
        "description": (
            "Verify that the weights, databases and official checkouts listed in "
            "src/task/step/steps/resources.json are installed. Emits one row per expected file with its "
            "presence and size, and records the installation command for anything missing."
        ),
        "category": "Data",
        "icon": "Database",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        resource = str(params.get("resource") or "").strip()
        root = str(params.get("root") or "").strip() or None
        strict = bool(params.get("strict") if params.get("strict") is not None else False)
        out_name = str(params.get("output") or "resources")

        if resource:
            checks = check_many([resource], root)
        else:
            checks = check_many(None, root)

        labels: list[str] = []
        rows: list[tuple[float, float]] = []
        missing: list[str] = []
        statuses: dict[str, str] = {}
        for identifier in sorted(checks):
            check = checks[identifier]
            statuses[identifier] = check["status"]
            if check["missing"]:
                missing.append(identifier)
            for name in sorted(check["files"]):
                info = check["files"][name]
                labels.append(f"{identifier}:{name}")
                rows.append((1.0 if info["present"] else 0.0, float(info["size_mb"])))

        if not rows:
            raise StepError("resource_preflight: the manifest lists no expected files")

        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=["file", "statistic"],
            labels={
                "file": {label: index for index, label in enumerate(labels)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "n_resources": len(checks),
                "n_files": len(labels),
                "n_missing": len(missing),
                "missing_resources": missing,
                "statuses": statuses,
                "manifest": str(manifest_path()),
                "missing_code": np.nan,
            },
        )
        out.validate()

        if strict and missing:
            descriptions = [remedy(checks[identifier]) for identifier in missing]
            raise StepError(
                "resource_preflight: missing resources: " + " | ".join(descriptions)
            )

        ctx[out_name] = out
        available = len(checks) - len(missing)
        self._export_data = {
            "n_resources": len(checks),
            "n_files": len(labels),
            "n_available": available,
            "n_missing": len(missing),
        }
        print(
            f"[resource_preflight] {available}/{len(checks)} resources available, "
            f"{len(labels)} files checked"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


def known_resources() -> dict[str, str]:
    """Convenience wrapper used by the CLI helper and tests."""

    return {identifier: resource.title for identifier, resource in load_resources().items()}
