"""Johansen trace and maximum-eigenvalue cointegration tests."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._cointegration_common import variables_matrix

_COLUMNS = [
    "trace_stat",
    "trace_crit_90",
    "trace_crit_95",
    "trace_crit_99",
    "max_eig_stat",
    "max_eig_crit_90",
    "max_eig_crit_95",
    "max_eig_crit_99",
    "eigenvalue",
]


class JohansenStep(Step):
    name = "johansen"
    title = "Johansen cointegration test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "det_order": {"type": "integer", "enum": [-1, 0, 1], "default": 0},
            "k_ar_diff": {"type": "integer", "minimum": 1, "default": 1},
            "output": {"type": "string"},
        },
        "required": [],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.tsa.vector_ar.vecm import coint_johansen

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        det_order = int(ctx.step_params.get("det_order", 0))
        k_ar_diff = int(ctx.step_params.get("k_ar_diff", 1))
        out_name = ctx.step_params.get("output", self.name)

        data, features, n = variables_matrix(inputs[0], sample_dim, feature_dim, self.name)
        if k_ar_diff >= n - 2:
            raise StepError(f"{self.name}: k_ar_diff must be less than n - 2")
        if k_ar_diff < 1:
            raise StepError(f"{self.name}: k_ar_diff must be at least 1")

        try:
            result = coint_johansen(data, det_order, k_ar_diff)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: Johansen computation failed: {exc}") from exc

        k = len(features)
        trace = np.asarray(result.trace_stat, dtype=np.float64)
        trace_crit = np.asarray(result.trace_stat_crit_vals, dtype=np.float64)
        max_eig = np.asarray(result.max_eig_stat, dtype=np.float64)
        max_crit = np.asarray(result.max_eig_stat_crit_vals, dtype=np.float64)
        eigenvalues = np.asarray(result.eig, dtype=np.float64)
        rows = np.column_stack(
            [
                trace,
                trace_crit[:, 0],
                trace_crit[:, 1],
                trace_crit[:, 2],
                max_eig,
                max_crit[:, 0],
                max_crit[:, 1],
                max_crit[:, 2],
                eigenvalues,
            ]
        )
        if rows.shape != (k, len(_COLUMNS)) or not np.isfinite(rows).all():
            raise StepError(f"{self.name}: invalid Johansen result")

        form = Form(
            rows,
            ["rank", "statistic"],
            {
                "rank": {f"r{rank}": rank for rank in range(k)},
                "statistic": {name: i for i, name in enumerate(_COLUMNS)},
            },
            {
                "missing_code": np.nan,
                "method": "Johansen",
                "det_order": det_order,
                "k_ar_diff": k_ar_diff,
                "variables": features,
                "n": n,
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export = {
            "variables": features,
            "det_order": det_order,
            "k_ar_diff": k_ar_diff,
            "n": n,
            "trace": trace.tolist(),
            "trace_critical": trace_crit.tolist(),
            "max_eig": max_eig.tolist(),
            "max_eig_critical": max_crit.tolist(),
            "eigenvalues": eigenvalues.tolist(),
        }
        print(
            f"[{self.name}] variables={len(features)}, "
            f"trace0={float(trace[0]):.4f}, max_eig0={float(max_eig[0]):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
