"""Nearest-neighbour propensity-score matching without replacement."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._causal_utils import column, treatment_vector


class PsmMatchStep(Step):
    """Match treated units to controls on the estimated propensity score."""

    provider = "operon-core"
    parameters_file = "psm_match.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "psm_match",
        "version": "1.0.0",
        "kind": "operator",
        "title": "psm_match",
        "description": "Caliper nearest-neighbour matching on propensity scores.",
        "category": "Causal Inference",
        "icon": "Users",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "field_dim", "default": "field"}],
                 "labels": []},
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "score_dim", "default": "statistic"}],
                 "labels": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.zeros(0)).nbytes) for item in inputs or [])
        return max(3 * size, 16 * 1024 ** 2), 4 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        operator = "psm_match"
        data, scores = inputs[0], inputs[1]
        sample_dim = params.get("sample_dim", "sample")
        field_dim = params.get("field_dim", "field")
        score_dim = params.get("score_dim", "statistic")
        treatment_field = params.get("treatment_field", "treat")
        score_field = params.get("score_field", "propensity")
        caliper = float(params.get("caliper", 0.2))
        ratio = int(params.get("ratio", 1))
        order = str(params.get("order", "largest"))
        if caliper < 0:
            raise StepError(f"{operator}: caliper must be non-negative")
        if ratio < 1:
            raise StepError(f"{operator}: ratio must be at least 1")
        y = treatment_vector(data, field_dim, treatment_field, operator)
        if getattr(scores.data, "ndim", 0) != 2:
            raise StepError(f"{operator}: propensity input must be two-dimensional")
        score_values = column(scores, score_dim, score_field, operator)
        data_names = list((data.labels.get(sample_dim, {}) or {}).keys())
        score_names = list((scores.labels.get(sample_dim, {}) or {}).keys())
        if data_names and score_names and data_names == score_names:
            aligned = score_values
        elif data_names and set(data_names) == set(score_names):
            lookup = {name: index for index, name in enumerate(score_names)}
            aligned = np.asarray([score_values[lookup[name]] for name in data_names])
        elif score_values.size == y.size:
            aligned = score_values
        else:
            raise StepError(f"{operator}: propensity rows do not align with samples")
        if not np.all(np.isfinite(aligned)):
            raise StepError(f"{operator}: propensity scores must be finite")
        spread = float(np.std(aligned, ddof=1))
        limit = caliper * spread if spread > 0 else 0.0
        treated = np.where(y == 1)[0]
        controls = np.where(y == 0)[0]
        if treated.size == 0 or controls.size == 0:
            raise StepError(f"{operator}: matching needs treated and control units")
        if order == "largest":
            treated = treated[np.argsort(-aligned[treated], kind="mergesort")]
        elif order == "smallest":
            treated = treated[np.argsort(aligned[treated], kind="mergesort")]
        elif order != "data":
            raise StepError(f"{operator}: order must be largest, smallest or data")
        available = np.ones(controls.size, dtype=bool)
        matched = np.zeros(y.size, dtype=bool)
        pair_ids = np.zeros(y.size, dtype=np.int64)
        pairs = 0
        for unit in treated:
            if not available.any():
                break
            distances = np.abs(aligned[controls] - aligned[unit])
            candidates = np.where(available & (distances <= limit))[0]
            if candidates.size == 0:
                continue
            chosen = candidates[np.argsort(distances[candidates], kind="mergesort")]
            chosen = chosen[:ratio]
            pairs += 1
            matched[unit] = True
            pair_ids[unit] = pairs
            for candidate in chosen:
                available[candidate] = False
                control = controls[candidate]
                matched[control] = True
                pair_ids[control] = pairs
        sample_labels = dict(data.labels.get(sample_dim, {}))
        if len(sample_labels) != y.size:
            sample_labels = {f"s{index}": index for index in range(y.size)}
        out = Form(
            np.column_stack([matched.astype(float), pair_ids.astype(float), aligned]),
            dims=[sample_dim, field_dim],
            labels={sample_dim: sample_labels,
                    field_dim: {"matched": 0, "pair_id": 1, "propensity": 2}},
            info={
                "n_treated": int(treated.size),
                "n_controls": int(controls.size),
                "n_pairs": int(pairs),
                "n_matched_units": int(np.sum(matched)),
                "n_unmatched_treated": int(treated.size - pairs),
                "caliper": caliper,
                "caliper_abs": float(limit),
                "score_sd": spread,
                "ratio": int(ratio),
                "order": order,
            },
        )
        out.validate()
        self._export_data = {
            "n_treated": int(treated.size),
            "n_controls": int(controls.size),
            "n_pairs": int(pairs),
            "n_matched_units": int(np.sum(matched)),
            "n_unmatched_treated": int(treated.size - pairs),
            "caliper": caliper,
            "caliper_abs": float(limit),
            "score_sd": spread,
        }
        ctx[params.get("output", "matched")] = out

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
