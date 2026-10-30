"""Hosmer-Lemeshow goodness-of-fit test for binary predictions."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame
from ._ext_common import make_form


class HosmerLemeshowStep(Step):
    name = "hosmer_lemeshow"
    title = "Hosmer-Lemeshow test"
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
            "probability_label": {"type": "string"},
            "groups": {"type": "integer", "minimum": 2, "default": 10},
            "output": {"type": "string"},
        },
        "required": ["outcome_label", "probability_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        outcome_label = ctx.step_params["outcome_label"]
        probability_label = ctx.step_params["probability_label"]
        groups = int(ctx.step_params.get("groups", 10))
        out_name = ctx.step_params.get("output", self.name)
        if groups < 2:
            raise StepError("hosmer_lemeshow: groups must be at least 2")
        frame = table_frame(form, sample_dim, feature_dim, "hosmer_lemeshow")
        outcome = numeric_column(frame, outcome_label, "hosmer_lemeshow")
        probability = numeric_column(frame, probability_label, "hosmer_lemeshow")
        keep = np.isfinite(outcome) & np.isfinite(probability)
        outcome, probability = outcome[keep], probability[keep]
        if outcome.size < groups:
            raise StepError("hosmer_lemeshow: fewer observations than groups")
        if not np.all(np.isin(outcome, (0.0, 1.0))):
            raise StepError("hosmer_lemeshow: outcome must be binary 0/1")
        if np.any(probability < 0.0) or np.any(probability > 1.0):
            raise StepError("hosmer_lemeshow: probabilities must lie in [0, 1]")

        # Match R ResourceSelection::hoslem.test: unique quantile breakpoints
        # with right-closed intervals, then observed/expected counts per bin.
        breaks = np.unique(np.quantile(probability, np.linspace(0.0, 1.0, groups + 1)))
        if breaks.size < 2:
            raise StepError("hosmer_lemeshow: probabilities have no spread")
        bins = np.searchsorted(breaks[1:-1], probability, side="left")
        n_bins = int(bins.max()) + 1
        if n_bins < 2:
            raise StepError("hosmer_lemeshow: fewer than two populated bins")

        statistic = 0.0
        for b in range(n_bins):
            mask = bins == b
            observed_1 = float(outcome[mask].sum())
            observed_0 = float(mask.sum()) - observed_1
            expected_1 = float(probability[mask].sum())
            expected_0 = float(mask.sum()) - expected_1
            for observed, expected in ((observed_0, expected_0), (observed_1, expected_1)):
                if expected > 0:
                    statistic += (observed - expected) ** 2 / expected
        df = n_bins - 2
        p = float(stats.chi2.sf(statistic, df)) if df > 0 else 1.0
        out = make_form(
            [[statistic], [float(df)], [p], [float(n_bins)], [float(outcome.size)]],
            ["statistic", "value"],
            {
                "statistic": {"statistic": 0, "df": 1, "p": 2, "n_bins": 3, "n": 4},
                "value": {"value": 0},
            },
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": float(statistic),
            "df": int(df),
            "p": p,
            "n_bins": n_bins,
            "n": int(outcome.size),
            "groups": groups,
        }
        print(f"[hosmer_lemeshow] chisq={statistic:.4f}, df={df}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
