"""Kendall's coefficient of concordance W."""
from __future__ import annotations

from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ordinal38_common import kendall_w
from ._stats20_common import scalar_form


class KendallWStep(Step):
    """Kendall's W with column-wise ranks and no tie correction."""

    name = "kendall_w"
    title = "Kendall's W"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("subject_dim", "subject"), param("rater_dim", "rater")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "subject_dim": {"type": "string", "default": "subject"},
            "rater_dim": {"type": "string", "default": "rater"},
            "raters": {"type": "array", "items": {"type": "string"}},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        subject_dim = ctx.step_params.get("subject_dim", "subject")
        rater_dim = ctx.step_params.get("rater_dim", "rater")
        raters = ctx.step_params.get("raters")
        out_name = ctx.step_params.get("output", self.name)
        w_value, chisq, df, p_value, s_value, selected, subjects, n_raters = kendall_w(
            form, subject_dim, rater_dim, raters, "kendall_w"
        )
        out = scalar_form(
            [w_value, chisq, float(df), p_value, s_value, float(subjects), float(n_raters)],
            ["W", "chisq", "df", "p", "S", "n_subjects", "n_raters"],
            "kendall_w",
        )
        out.info.update({"raters": selected, "tie_correction": False})
        ctx[out_name] = out
        self._export_data = {
            "W": w_value,
            "chisq": chisq,
            "df": int(df),
            "p": p_value,
            "S": s_value,
            "n_subjects": int(subjects),
            "n_raters": int(n_raters),
            "raters": selected,
        }
        print(f"[kendall_w] W={w_value:.6f}, chisq={chisq:.6f}, df={df}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
