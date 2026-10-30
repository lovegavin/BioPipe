"""Logistic calibration intercept and slope for binary risk predictions."""
from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from statsmodels.genmod.families import Binomial

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._clinical22_common import binary_prediction_table
from ._ext_common import make_form


class CalibrationSlopeStep(Step):
    name = "calibration_slope"
    title = "Calibration intercept and slope"
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
            "risk_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["outcome_label", "risk_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        outcome_label = ctx.step_params["outcome_label"]
        risk_label = ctx.step_params["risk_label"]
        out_name = ctx.step_params.get("output", self.name)
        outcome, (risk,) = binary_prediction_table(
            inputs[0], sample_dim, feature_dim, outcome_label, risk_label, label=self.name
        )
        probability = np.clip(risk, 1e-12, 1.0 - 1e-12)
        linear = np.log(probability / (1.0 - probability))
        n = int(outcome.size)

        # Calibration-in-the-large: observed outcome on an offset of the
        # predicted linear predictor.  Calibration slope: coefficient of lp in
        # logit(P(y=1)) = a + b * lp.
        intercept_fit = sm.GLM(
            outcome, np.ones((n, 1)), family=Binomial(), offset=linear
        ).fit()
        slope_fit = sm.GLM(
            outcome, np.column_stack([np.ones(n), linear]), family=Binomial()
        ).fit()
        intercept = float(intercept_fit.params[0])
        intercept_se = float(intercept_fit.bse[0])
        intercept_z = float(intercept_fit.tvalues[0])
        intercept_p = float(intercept_fit.pvalues[0])
        slope = float(slope_fit.params[1])
        slope_se = float(slope_fit.bse[1])
        slope_z = float(slope_fit.tvalues[1])
        slope_p = float(slope_fit.pvalues[1])
        if not np.all(np.isfinite([intercept, intercept_se, slope, slope_se])):
            raise StepError("calibration_slope: model did not converge")

        rows = [
            ("calibration_intercept", intercept),
            ("intercept_se", intercept_se),
            ("intercept_z", intercept_z),
            ("intercept_p", intercept_p),
            ("calibration_slope", slope),
            ("slope_se", slope_se),
            ("slope_z", slope_z),
            ("slope_p", slope_p),
            ("n", float(n)),
            ("events", float(np.sum(outcome))),
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
            "calibration_intercept": intercept,
            "calibration_slope": slope,
            "slope_se": slope_se,
            "n": n,
            "events": int(np.sum(outcome)),
        }
        print(
            f"[{self.name}] intercept={intercept:.4f}, slope={slope:.4f}, "
            f"n={n}, events={int(np.sum(outcome))}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
