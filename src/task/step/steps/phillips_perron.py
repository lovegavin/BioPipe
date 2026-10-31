"""Phillips-Perron unit-root test for a univariate series."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class PhillipsPerronStep(Step):
    """Phillips-Perron Z-tau test with Newey-West long-run variance."""

    name = "phillips_perron"
    title = "Phillips-Perron unit-root test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["arch>=6"]
    dependency_imports = ["arch"]
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
            "value_label": {"type": "string"},
            "lags": {"type": ["integer", "null"], "minimum": 0, "default": None},
            "trend": {"type": "string", "enum": ["c", "ct"], "default": "c"},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from arch.unitroot import PhillipsPerron

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        trend = ctx.step_params.get("trend", "c")
        lags = ctx.step_params.get("lags")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 10:
            raise StepError(f"{self.name}: need at least 10 finite values")
        if np.ptp(values) <= 0:
            raise StepError(f"{self.name}: series must have positive variance")
        if lags is not None and int(lags) >= n - 2:
            raise StepError(f"{self.name}: lags must be less than n - 2")

        try:
            result = PhillipsPerron(
                values,
                lags=None if lags is None else int(lags),
                trend=trend,
                test_type="tau",
            )
        except (ValueError, np.linalg.LinAlgError, RuntimeError) as exc:
            raise StepError(f"{self.name}: Phillips-Perron computation failed: {exc}") from exc

        critical = {key: float(value) for key, value in result.critical_values.items()}
        rows = [
            ("statistic", float(result.stat)),
            ("p", float(result.pvalue)),
            ("lags", float(result.lags)),
            ("nobs", float(result.nobs)),
            ("n", float(n)),
            ("critical_1pct", critical["1%"]),
            ("critical_5pct", critical["5%"]),
            ("critical_10pct", critical["10%"]),
        ]
        names = [name for name, _ in rows]
        form = Form(
            data=np.asarray([[value] for _, value in rows], dtype=np.float64),
            dims=["statistic", "value"],
            labels={"statistic": {name: i for i, name in enumerate(names)}, "value": {"value": 0}},
            info={
                "missing_code": np.nan,
                "method": "Phillips-Perron Z-tau",
                "trend": trend,
                "lags": int(result.lags),
                "lags_rule": "fixed" if lags is not None else "aic",
                "critical": critical,
                "n": n,
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "statistic": float(result.stat),
            "p": float(result.pvalue),
            "lags": int(result.lags),
            "nobs": int(result.nobs),
            "n": n,
            "trend": trend,
            "critical": critical,
        }
        print(f"[{self.name}] statistic={float(result.stat):.6f}, p={float(result.pvalue):.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
