"""Intraclass correlation coefficients, ported from R irr::icc."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._stats20_common import scalar_form
from src.task.step.steps._stats21_common import numeric_column, table_frame
from ._agreement32_common import icc_from_matrix


_NAMES = [
    "subjects", "raters", "icc", "f", "df1", "df2", "p",
    "ci_low", "ci_high", "msr", "msc", "mse",
]


class IntraclassCorrelationStep(Step):
    name = "intraclass_correlation"
    title = "Intraclass correlation"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.10"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "raters": {"type": "array", "items": {"type": "string"}},
            "model": {"type": "string", "enum": ["oneway", "twoway"], "default": "twoway"},
            "type": {"type": "string", "enum": ["consistency", "agreement"], "default": "agreement"},
            "unit": {"type": "string", "enum": ["single", "average"], "default": "single"},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        frame = table_frame(inputs[0], sample_dim, feature_dim, "intraclass_correlation")
        raters = ctx.step_params.get("raters")
        if raters:
            missing = [name for name in raters if name not in frame.columns]
            if missing:
                raise StepError(f"intraclass_correlation: rater columns not found: {missing}")
            names = list(raters)
        else:
            names = [name for name in frame.columns if name != "__sample__"]
        if len(names) < 2:
            raise StepError("intraclass_correlation: need at least two rater columns")
        if len(set(names)) != len(names):
            raise StepError("intraclass_correlation: rater columns must be unique")
        columns = [numeric_column(frame, name, "intraclass_correlation") for name in names]
        ratings = np.column_stack(columns)
        keep = np.isfinite(ratings).all(axis=1)
        ratings = ratings[keep]
        if ratings.shape[0] < 3:
            raise StepError("intraclass_correlation: need at least three complete subjects")

        result = icc_from_matrix(
            ratings,
            ctx.step_params.get("model", "twoway"),
            ctx.step_params.get("type", "agreement"),
            ctx.step_params.get("unit", "single"),
            float(ctx.step_params.get("confidence", 0.95)),
        )
        form = scalar_form([result[name] for name in _NAMES], _NAMES, "intraclass_correlation")
        form.info.update({
            "method": "ICC",
            "model": result["model"],
            "type": result["type"],
            "unit": result["unit"],
            "confidence": result["confidence"],
        })
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "icc": result["icc"], "f": result["f"], "p": result["p"],
            "ci_low": result["ci_low"], "ci_high": result["ci_high"],
            "subjects": int(result["subjects"]), "raters": int(result["raters"]),
            "model": result["model"], "type": result["type"], "unit": result["unit"],
        }
        print(f"[intraclass_correlation] icc={result['icc']:.6g} p={result['p']:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
