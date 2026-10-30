"""Stuart-Maxwell test for marginal homogeneity in a square table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import table_frame
from ._ext_common import make_form


class StuartMaxwellStep(Step):
    """Test whether two raters have the same marginal distribution."""

    name = "stuart_maxwell"
    title = "Stuart-Maxwell test"
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
            "rater_a": {"type": "string"},
            "rater_b": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["rater_a", "rater_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        a_name = ctx.step_params["rater_a"]
        b_name = ctx.step_params["rater_b"]
        out_name = ctx.step_params.get("output", self.name)
        if a_name == b_name:
            raise StepError("stuart_maxwell: rater_a and rater_b must differ")
        frame = table_frame(form, sample_dim, feature_dim, "stuart_maxwell")
        if a_name not in frame.columns or b_name not in frame.columns:
            raise StepError("stuart_maxwell: rater columns not found")
        a = frame[a_name].to_numpy(dtype=object)
        b = frame[b_name].to_numpy(dtype=object)
        keep = np.array([_present(x) and _present(y) for x, y in zip(a, b)])
        a, b = a[keep], b[keep]
        if a.size < 2:
            raise StepError("stuart_maxwell: fewer than two complete pairs")
        categories = sorted({str(v) for v in a} | {str(v) for v in b})
        k = len(categories)
        if k < 2:
            raise StepError("stuart_maxwell: at least two categories are required")
        index = {name: i for i, name in enumerate(categories)}
        table = np.zeros((k, k), dtype=np.float64)
        for left, right in zip(a, b):
            table[index[str(left)], index[str(right)]] += 1.0

        # Match DescTools::StuartMaxwellTest: remove categories whose
        # diagonal equals both margins before constructing the covariance.
        row = table.sum(axis=1)
        col = table.sum(axis=0)
        keep_cat = ~((np.diag(table) == row) & (np.diag(table) == col))
        table = table[np.ix_(keep_cat, keep_cat)]
        r = table.shape[0]
        if r < 2:
            raise StepError("stuart_maxwell: too many equal marginals")
        row = table.sum(axis=1)
        col = table.sum(axis=0)
        delta = (row - col)[: r - 1]
        covariance = np.zeros((r - 1, r - 1), dtype=np.float64)
        for i in range(r - 1):
            for j in range(r - 1):
                if i == j:
                    covariance[i, j] = row[i] + col[i] - 2.0 * table[i, i]
                else:
                    covariance[i, j] = -(table[i, j] + table[j, i])
        if abs(np.linalg.det(covariance)) < 1e-12:
            raise StepError("stuart_maxwell: covariance matrix is singular")
        statistic = float(delta @ np.linalg.solve(covariance, delta))
        df = r - 1
        p = float(stats.chi2.sf(statistic, df))
        out = make_form(
            [
                [statistic],
                [float(df)],
                [p],
                [float(a.size)],
                [float(k)],
            ],
            ["statistic", "value"],
            {
                "statistic": {
                    "statistic": 0,
                    "df": 1,
                    "p": 2,
                    "n": 3,
                    "n_categories": 4,
                },
                "value": {"value": 0},
            },
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic,
            "df": int(df),
            "p": p,
            "n": int(a.size),
            "n_categories": k,
        }
        print(f"[stuart_maxwell] chisq={statistic:.4f}, df={df}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _present(value) -> bool:
    if value is None:
        return False
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return str(value).strip() not in {"", "nan", "None"}
