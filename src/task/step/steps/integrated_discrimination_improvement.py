"""Integrated discrimination improvement for two binary risk predictions."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._clinical22_common import binary_prediction_table
from ._ext_common import make_form


class IntegratedDiscriminationImprovementStep(Step):
    name = "integrated_discrimination_improvement"
    title = "Integrated discrimination improvement"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": False,
            "axis_info_open": False,
            "info": {"missing_code": {"type": ["number", "null"]}},
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "outcome_label": {"type": "string"},
            "old_risk_label": {"type": "string"},
            "new_risk_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["outcome_label", "old_risk_label", "new_risk_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        outcome_label = ctx.step_params["outcome_label"]
        old_label = ctx.step_params["old_risk_label"]
        new_label = ctx.step_params["new_risk_label"]
        out_name = ctx.step_params.get("output", self.name)
        outcome, (old, new) = binary_prediction_table(
            inputs[0],
            sample_dim,
            feature_dim,
            outcome_label,
            old_label,
            new_label,
            label=self.name,
        )
        events = outcome == 1.0
        nonevents = ~events
        old_discrimination = float(old[events].mean() - old[nonevents].mean())
        new_discrimination = float(new[events].mean() - new[nonevents].mean())
        idi = new_discrimination - old_discrimination
        if not np.isfinite(idi):
            raise StepError(f"{self.name}: IDI is not finite")
        rows = [
            ("idi", idi),
            ("old_discrimination", old_discrimination),
            ("new_discrimination", new_discrimination),
            ("n_events", float(events.sum())),
            ("n_nonevents", float(nonevents.sum())),
            ("n", float(outcome.size)),
        ]
        ctx[out_name] = make_form(
            [[value] for _, value in rows],
            ["statistic", "value"],
            {
                "statistic": {name: i for i, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
        )
        self._export = {
            "idi": idi,
            "old_discrimination": old_discrimination,
            "new_discrimination": new_discrimination,
            "n": int(outcome.size),
        }
        print(f"[{self.name}] IDI={idi:.4f}, n={outcome.size}")

    def export(self, ctx: Context) -> dict:
        return self._export
