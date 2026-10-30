"""Continuous net reclassification improvement for two risk predictions."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._clinical22_common import binary_prediction_table
from ._ext_common import make_form


class NetReclassificationImprovementStep(Step):
    name = "net_reclassification_improvement"
    title = "Continuous net reclassification improvement"
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
        up = new > old + 1e-12
        down = new < old - 1e-12
        events = outcome == 1.0
        nonevents = ~events
        n_events = int(events.sum())
        n_nonevents = int(nonevents.sum())
        if n_events == 0 or n_nonevents == 0:
            raise StepError(f"{self.name}: both outcome classes are required")

        events_up = float(up[events].mean())
        events_down = float(down[events].mean())
        nonevents_up = float(up[nonevents].mean())
        nonevents_down = float(down[nonevents].mean())
        nri = (events_up - events_down) + (nonevents_down - nonevents_up)
        if not np.isfinite(nri):
            raise StepError(f"{self.name}: NRI is not finite")
        rows = [
            ("nri", nri),
            ("events_up_rate", events_up),
            ("events_down_rate", events_down),
            ("nonevents_up_rate", nonevents_up),
            ("nonevents_down_rate", nonevents_down),
            ("n_events", float(n_events)),
            ("n_nonevents", float(n_nonevents)),
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
            "nri": nri,
            "events_up_rate": events_up,
            "events_down_rate": events_down,
            "nonevents_up_rate": nonevents_up,
            "nonevents_down_rate": nonevents_down,
            "n": int(outcome.size),
        }
        print(f"[{self.name}] NRI={nri:.4f}, n={outcome.size}, events={n_events}")

    def export(self, ctx: Context) -> dict:
        return self._export
