"""Linear mixed-effects model with a random intercept."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats21_common import design_matrix, numeric_column, table_frame


class LinearMixedModelStep(Step):
    """Random-intercept linear mixed model via statsmodels MixedLM."""

    name = "linear_mixed_model"
    title = "Linear mixed model"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("feature_dim", "feature")],
        )
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "response_label": {"type": "string"},
            "fixed_effects": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "group_label": {"type": "string"},
            "categorical": {"type": "array", "items": {"type": "string"}},
            "reml": {"type": "boolean", "default": True},
            "maxiter": {"type": "integer", "minimum": 20, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["response_label", "fixed_effects", "group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.regression.mixed_linear_model import MixedLM

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        frame = table_frame(form, sample_dim, feature_dim, "linear_mixed_model")
        response_label = ctx.step_params["response_label"]
        fixed = list(ctx.step_params["fixed_effects"])
        group_label = ctx.step_params["group_label"]
        categorical = list(ctx.step_params.get("categorical", []))
        missing = [name for name in categorical if name not in fixed]
        if missing:
            raise StepError(
                f"linear_mixed_model: categorical names not in fixed_effects: {missing}"
            )
        for name in [response_label, group_label, *fixed]:
            if name not in frame.columns:
                raise StepError(f"linear_mixed_model: column {name!r} not found")

        valid = frame[response_label].notna() & frame[group_label].notna()
        for name in fixed:
            if name in categorical:
                valid &= frame[name].notna()
            else:
                valid &= np.isfinite(
                    __import__("pandas").to_numeric(frame[name], errors="coerce")
                )
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 8:
            raise StepError("linear_mixed_model: fewer than eight complete rows")
        y = numeric_column(frame, response_label, "linear_mixed_model")
        if not np.isfinite(y).all():
            raise StepError("linear_mixed_model: response must be numeric")
        groups = frame[group_label].astype(str).to_numpy()
        if len(set(groups)) < 2:
            raise StepError("linear_mixed_model: need at least two groups")
        counts = {g: int((groups == g).sum()) for g in set(groups)}
        if min(counts.values()) < 2:
            raise StepError("linear_mixed_model: every group needs at least two rows")
        x, names = design_matrix(
            frame, fixed, categorical, "linear_mixed_model"
        )
        if x.shape[0] <= x.shape[1] + 1:
            raise StepError("linear_mixed_model: too few rows for the fixed design")

        try:
            model = MixedLM(
                y,
                x,
                groups=groups,
                exog_re=np.ones((len(y), 1), dtype=np.float64),
            )
            result = model.fit(
                reml=bool(ctx.step_params.get("reml", True)),
                method="lbfgs",
                maxiter=int(ctx.step_params.get("maxiter", 200)),
            )
        except Exception as exc:
            raise StepError(f"linear_mixed_model: fit failed: {exc}") from exc

        coef = np.asarray(result.fe_params, dtype=np.float64)
        se = np.asarray(result.bse_fe, dtype=np.float64)
        pvals = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        n_terms = x.shape[1]
        if len(coef) != n_terms:
            raise StepError("linear_mixed_model: unexpected fixed-effect length")
        group_var = float(np.asarray(result.cov_re, dtype=np.float64)[0, 0])
        residual = float(result.scale)
        icc = group_var / (group_var + residual) if group_var + residual > 0 else np.nan
        rows = []
        for i, term in enumerate(names):
            z = coef[i] / se[i] if se[i] > 0 else np.nan
            rows.append(
                [
                    coef[i],
                    se[i],
                    z,
                    pvals[i] if i < len(pvals) else np.nan,
                    conf[i, 0],
                    conf[i, 1],
                ]
            )
        for term, value in [
            ("group_var", group_var),
            ("residual_var", residual),
            ("icc", icc),
            ("n_groups", float(len(set(groups)))),
            ("n_obs", float(len(y))),
        ]:
            rows.append([value, np.nan, np.nan, np.nan, np.nan, np.nan])
        terms = names + ["group_var", "residual_var", "icc", "n_groups", "n_obs"]
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["term", "statistic"],
            labels={
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                },
            },
            info={
                "missing_code": np.nan,
                "reml": bool(ctx.step_params.get("reml", True)),
                "n": int(len(y)),
                "n_groups": int(len(set(groups))),
                "group_var": group_var,
                "residual_var": residual,
                "icc": icc,
                "loglike": float(result.llf),
            },
        )
        self._export_data = {
            "n": int(len(y)),
            "n_groups": int(len(set(groups))),
            "group_var": group_var,
            "residual_var": residual,
            "icc": icc,
            "loglike": float(result.llf),
            "terms": terms,
        }
        print(
            f"[linear_mixed_model] n={len(y)}, groups={len(set(groups))}, "
            f"ICC={icc:.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
