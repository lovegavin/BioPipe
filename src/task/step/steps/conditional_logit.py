"""Conditional logistic regression for matched strata."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._regression30_common import coefficient_rows, drop_intercept, require_binary
from ._stats21_common import design_matrix, numeric_column, table_frame


class ConditionalLogitStep(Step):
    """Fixed-effects logistic regression for matched case-control strata."""

    name = "conditional_logit"
    title = "Conditional logistic regression"
    category = "Statistics"
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
            "stratum_label": {"type": "string"},
            "event_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "maxiter": {"type": "integer", "minimum": 20, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["stratum_label", "event_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.discrete.conditional_models import ConditionalLogit

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        stratum_label = ctx.step_params["stratum_label"]
        event_label = ctx.step_params["event_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        missing = [name for name in categorical if name not in predictors]
        if missing:
            raise StepError(
                f"{self.name}: categorical names not in predictors: {missing}"
            )
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        for name in [stratum_label, event_label, *predictors]:
            if name not in frame.columns:
                raise StepError(f"{self.name}: column {name!r} not found")

        valid = frame[[stratum_label, event_label]].notna().all(axis=1).to_numpy()
        for name in predictors:
            if name in categorical:
                valid &= frame[name].notna().to_numpy()
            else:
                valid &= np.isfinite(numeric_column(frame, name, self.name))
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 6:
            raise StepError(f"{self.name}: fewer than six complete rows")

        event = require_binary(
            numeric_column(frame, event_label, self.name), self.name
        )
        strata = [str(value) for value in frame[stratum_label].tolist()]
        order = {value: i for i, value in enumerate(sorted(set(strata)))}
        groups = np.asarray([order[value] for value in strata], dtype=np.int64)
        for group in np.unique(groups):
            selected = event[groups == group]
            if int(selected.sum()) != 1:
                raise StepError(
                    f"{self.name}: every stratum must contain exactly one event"
                )
            if selected.size < 2:
                raise StepError(f"{self.name}: every stratum needs a control")

        design, terms = design_matrix(frame, predictors, categorical, self.name)
        design, terms = drop_intercept(design, terms)
        if not terms:
            raise StepError(f"{self.name}: no predictor columns remain")
        maxiter = int(ctx.step_params.get("maxiter", 200))
        try:
            result = ConditionalLogit(event, design, groups=groups).fit(
                disp=False, maxiter=maxiter
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        rows = coefficient_rows(params, bse, pvalues, conf, terms, ratios=True)
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
                    "odds_ratio": 6,
                    "OR_CI_low": 7,
                    "OR_CI_high": 8,
                },
            },
            info={
                "method": "conditional logistic",
                "n": int(len(event)),
                "n_groups": int(len(np.unique(groups))),
                "llf": float(result.llf),
            },
        )
        self._export = {
            "terms": terms,
            "coef": [float(value) for value in params],
            "se": [float(value) for value in bse],
            "p": [float(value) for value in pvalues],
            "odds_ratio": [float(value) for value in np.exp(params)],
            "llf": float(result.llf),
            "n": int(len(event)),
            "n_groups": int(len(np.unique(groups))),
        }
        print(
            f"[{self.name}] n={len(event)}, groups={len(np.unique(groups))}, "
            f"terms={len(terms)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
