"""White heteroskedasticity test for an OLS regression."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._stats21_common import design_matrix, numeric_column, table_frame


class WhiteTestStep(Step):
    name = "white_test"
    title = "White heteroskedasticity test"
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
            "response_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
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
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        y = numeric_column(frame, response_label, self.name)
        keep = np.isfinite(y)
        for name in predictors:
            keep &= np.isfinite(numeric_column(frame, name, self.name))
        frame = frame.loc[keep].reset_index(drop=True)
        y = numeric_column(frame, response_label, self.name)
        X, names = design_matrix(frame, predictors, [], self.name)
        n, k = X.shape
        if n <= k + 2:
            raise StepError(f"{self.name}: not enough observations for the auxiliary regression")
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        resid = y - X @ beta
        z = X[:, 1:]
        parts = [np.ones((n, 1)), z, z * z]
        for i in range(z.shape[1]):
            for j in range(i + 1, z.shape[1]):
                parts.append((z[:, i] * z[:, j]).reshape(-1, 1))
        aux = np.column_stack(parts)
        aux_beta = np.linalg.lstsq(aux, resid * resid, rcond=None)[0]
        fitted = aux @ aux_beta
        centered = resid * resid - (resid * resid).mean()
        ss_tot = float(np.sum(centered * centered))
        if ss_tot <= 0:
            raise StepError(f"{self.name}: squared residuals have no variation")
        r2 = 1.0 - float(np.sum((resid * resid - fitted) ** 2)) / ss_tot
        df = aux.shape[1] - 1
        lm = n * r2
        p = float(stats.chi2.sf(lm, df))
        f_stat = (r2 / df) / ((1.0 - r2) / (n - df - 1)) if r2 < 1.0 else float("inf")
        f_p = float(stats.f.sf(f_stat, df, n - df - 1)) if r2 < 1.0 else 0.0
        rows = [
            ("lm_statistic", lm),
            ("lm_df", float(df)),
            ("lm_p", p),
            ("f_statistic", f_stat),
            ("f_df1", float(df)),
            ("f_df2", float(n - df - 1)),
            ("f_p", f_p),
            ("n", float(n)),
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
            "lm_statistic": lm,
            "lm_p": p,
            "f_statistic": f_stat,
            "f_p": f_p,
            "df": df,
            "n": n,
        }
        print(f"[{self.name}] LM={lm:.4f}, df={df}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
