"""Woolf test for homogeneity of odds ratios."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form, table


class WoolfTestStep(Step):
    """Woolf test for homogeneity of odds ratios across 2x2 strata."""

    name = "woolf_test"
    title = "Woolf test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("stratum_dim", "stratum"), param("feature_dim", "feature")])
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "stratum_dim": {"type": "string", "default": "stratum"},
            "feature_dim": {"type": "string", "default": "feature"},
            "a_label": {"type": "string", "default": "a"},
            "b_label": {"type": "string", "default": "b"},
            "c_label": {"type": "string", "default": "c"},
            "d_label": {"type": "string", "default": "d"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        stratum_dim = ctx.step_params.get("stratum_dim", "stratum")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        labels = [ctx.step_params.get(key, key.replace("_label", "")) for key in ("a_label", "b_label", "c_label", "d_label")]
        counts, strata, columns = table(form, stratum_dim, feature_dim, "woolf_test")
        if counts.ndim != 2 or counts.shape[1] != 4:
            raise StepError("woolf_test: table must have exactly four count columns a,b,c,d")
        if counts.shape[0] < 2:
            raise StepError("woolf_test: at least two strata are required")
        if (counts < 0).any():
            raise StepError("woolf_test: counts must be non-negative")
        if any(label not in columns for label in labels):
            raise StepError(f"woolf_test: count columns {labels!r} not found")
        counts = counts[:, [columns.index(label) for label in labels]].astype(np.float64)
        corrected = bool((counts == 0).any())
        if corrected:
            counts = counts + 0.5
        total = float(counts.sum())
        if total <= 0:
            raise StepError("woolf_test: table is empty")
        odds = (counts[:, 0] * counts[:, 3]) / (counts[:, 1] * counts[:, 2])
        if not np.isfinite(odds).all() or (odds <= 0).any():
            raise StepError("woolf_test: odds ratios must be finite and positive")
        weights = 1.0 / np.sum(1.0 / counts, axis=1)
        log_odds = np.log(odds)
        pooled = float(np.sum(weights * log_odds) / np.sum(weights))
        statistic = float(np.sum(weights * (log_odds - pooled) ** 2))
        df = counts.shape[0] - 1
        p_value = float(stats.chi2.sf(statistic, df))
        out = scalar_form(
            [statistic, float(df), p_value, float(counts.shape[0]), total, float(np.exp(pooled))],
            ["statistic", "df", "p", "n_strata", "n_total", "pooled_or"],
            "woolf_test",
        )
        out.info.update({
            "cells": labels,
            "odds_ratios": [float(value) for value in odds],
            "weights": [float(value) for value in weights],
            "zero_correction": corrected,
        })
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "df": df, "p": p_value,
            "n_strata": int(counts.shape[0]), "n_total": total,
            "pooled_or": float(np.exp(pooled)),
            "odds_ratios": [float(value) for value in odds],
        }
        print(f"[woolf_test] X2={statistic:.6f}, df={df}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
