"""boltz_affinity_summary: parse Boltz-2 affinity predictions."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

STATISTICS = ("affinity_pred_value", "affinity_probability_binary")
_REQUIRED = STATISTICS


def parse_affinity(path: Path) -> dict:
    """Read one Boltz affinity JSON file."""

    if not path.is_file():
        raise StepError(f"boltz_affinity_summary: affinity file {path} is not a file")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise StepError(f"boltz_affinity_summary: {path.name} is not valid JSON: {exc}") from exc
    missing = [key for key in _REQUIRED if key not in payload]
    if missing:
        raise StepError(f"boltz_affinity_summary: {path.name} is missing {', '.join(missing)}")
    summary = {
        "name": path.stem.removeprefix("affinity_"),
        "affinity_pred_value": float(payload["affinity_pred_value"]),
        "affinity_probability_binary": float(payload["affinity_probability_binary"]),
    }
    for suffix in ("1", "2"):
        value_key = f"affinity_pred_value{suffix}"
        probability_key = f"affinity_probability_binary{suffix}"
        if value_key in payload and probability_key in payload:
            summary[value_key] = float(payload[value_key])
            summary[probability_key] = float(payload[probability_key])
    return summary


def collect_affinity(path: Path) -> list[dict]:
    """Read one affinity JSON or every ``affinity_*.json`` under a directory."""

    if path.is_dir():
        files = sorted(path.rglob("affinity_*.json"))
        if not files:
            raise StepError(f"boltz_affinity_summary: no affinity_*.json under {path}")
        return [parse_affinity(item) for item in files]
    return [parse_affinity(path)]


def affinity_rows(summaries: list[dict]) -> list[dict]:
    """Flatten parsed summaries into table rows."""

    return [
        {
            "name": summary["name"],
            "affinity_pred_value": summary["affinity_pred_value"],
            "affinity_probability_binary": summary["affinity_probability_binary"],
            "has_variants": float("affinity_pred_value1" in summary and "affinity_pred_value2" in summary),
        }
        for summary in summaries
    ]


def best_summary(summaries: list[dict]) -> dict:
    """Return the most confident prediction (highest binder probability)."""

    best = max(summaries, key=lambda item: item["affinity_probability_binary"])
    return {
        "best_name": best["name"],
        "best_value": best["affinity_pred_value"],
        "best_probability": best["affinity_probability_binary"],
        "n_predictions": len(summaries),
    }


class BoltzAffinitySummaryStep(Step):
    provider = "operon-core"
    parameters_file = "boltz_affinity_summary.BoltzAffinitySummaryStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "boltz_affinity_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Boltz-2 亲和力预测汇总",
        "description": (
            "Read Boltz-2 affinity_*.json files and tabulate the predicted binding "
            "affinity value and binder probability, with the best prediction in info."
        ),
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "boltz"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        raw = str(params.get("affinity_path", "")).strip()
        if not raw:
            raise StepError("boltz_affinity_summary: affinity_path is required")
        path = Path(raw).expanduser()
        if not path.exists():
            raise StepError(f"boltz_affinity_summary: affinity_path {path} does not exist")
        summaries = collect_affinity(path)
        rows = affinity_rows(summaries)
        columns = ("affinity_pred_value", "affinity_probability_binary", "has_variants")
        data = np.zeros((len(rows), len(columns)), dtype=np.float32)
        for index, row in enumerate(rows):
            data[index] = [row[name] for name in columns]
        model_dim = str(params.get("model_dim", "complex"))
        out_name = str(params.get("output", "affinity"))
        ctx[out_name] = Form(
            data=data,
            dims=[model_dim, "statistic"],
            labels={
                model_dim: {row["name"]: index for index, row in enumerate(rows)},
                "statistic": {name: index for index, name in enumerate(columns)},
            },
            info={"missing_code": np.nan, **best_summary(summaries), "summaries": summaries},
        )
        self._export_data = {"rows": rows, "summaries": summaries, "best": best_summary(summaries)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
