"""Chow structural-break test for an OLS regression."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import design_matrix, numeric_column, table_frame


def _rss(y: np.ndarray, x: np.ndarray) -> float:
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    resid = y - x @ beta
    return float(np.sum(resid * resid))


class ChowTestStep(Step):
    name = "chow_test"
    title = "Chow structural-break test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "response_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "break_fraction": {"type": "number", "minimum": 0.1, "maximum": 0.9, "default": 0.5},
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        fraction = float(ctx.step_params.get("break_fraction", 0.5))
        out_name = ctx.step_params.get("output", self.name)
        if not 0.1 <= fraction <= 0.9:
            raise StepError("chow_test: break_fraction must lie in [0.1, 0.9]")
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        y = numeric_column(frame, response_label, self.name)
        keep = np.isfinite(y)
        for name in predictors:
            keep &= np.isfinite(numeric_column(frame, name, self.name))
        frame = frame.loc[keep].reset_index(drop=True)
        y = numeric_column(frame, response_label, self.name)
        x, names = design_matrix(frame, predictors, [], self.name)
        n, k = x.shape
        cut = int(round(n * fraction))
        if cut < k + 1 or n - cut < k + 1:
            raise StepError("chow_test: break leaves too few observations in one segment")
        rss_pooled = _rss(y, x)
        rss1 = _rss(y[:cut], x[:cut])
        rss2 = _rss(y[cut:], x[cut:])
        df1 = k
        df2 = n - 2 * k
        if df2 <= 0:
            raise StepError("chow_test: not enough residual degrees of freedom")
        denom = (rss1 + rss2) / df2
        if denom <= 0:
            raise StepError("chow_test: zero residual variance in a segment")
        f_stat = ((rss_pooled - rss1 - rss2) / df1) / denom
        f_stat = max(0.0, float(f_stat))
        p = float(stats.f.sf(f_stat, df1, df2))
        vals = [
            ("F", f_stat),
            ("df1", float(df1)),
            ("df2", float(df2)),
            ("p", p),
            ("rss_pooled", rss_pooled),
            ("rss1", rss1),
            ("rss2", rss2),
            ("n", float(n)),
            ("break_index", float(cut)),
        ]
        ctx[out_name] = scalar_form([value for _, value in vals], [name for name, _ in vals], "chow_test")
        self._export = {
            "F": f_stat,
            "df1": df1,
            "df2": df2,
            "p": p,
            "rss_pooled": rss_pooled,
            "rss1": rss1,
            "rss2": rss2,
            "n": n,
            "break_index": cut,
        }
        print(f"[{self.name}] F={f_stat:.4f}, df=({df1},{df2}), p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
