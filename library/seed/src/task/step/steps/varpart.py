"""Variance partitioning between two explanatory tables."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import reorder, require_dims


def _standardize(matrix, label):
    std = matrix.std(axis=0, ddof=1)
    if np.any(~np.isfinite(std)) or np.any(std <= 0.0):
        raise StepError(f"varpart: {label} contains a constant column")
    return (matrix - matrix.mean(axis=0)) / std


def _fit(response, predictors, ss_total, label):
    rank = int(np.linalg.matrix_rank(predictors))
    n = response.shape[0]
    if rank == 0:
        raise StepError(f"varpart: {label} carries no variation")
    if n - rank - 1 <= 0:
        raise StepError(
            f"varpart: {label} has rank {rank} with only {n} samples; "
            "adjusted R2 is undefined"
        )
    coef, *_ = np.linalg.lstsq(predictors, response, rcond=None)
    fitted = predictors @ coef
    r2 = float(np.sum(fitted * fitted) / ss_total)
    adjusted = float(1.0 - (1.0 - r2) * (n - 1) / (n - rank - 1))
    return r2, adjusted, rank


class VarpartStep(Step):
    provider = "operon-microbiome"
    parameters_file = "varpart.VarpartStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "varpart",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Variance partitioning",
        "category": "Omics",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "response_dim", "default": "response"}],
                 "labels": [], "parallel": []},
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "predictor_dim", "default": "predictor"}],
                 "labels": [], "parallel": []},
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "predictor_b_dim", "default": "predictor_b"}],
                 "labels": [], "parallel": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True,
                                  "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 3,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Variance partitioning of a response matrix between two predictor "
            "tables, reported as adjusted R2 fractions [a], [b], [c] and [d] "
            "following vegan varpart."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        response, first, second = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        response_dim = ctx.step_params.get("response_dim", "response")
        predictor_dim = ctx.step_params.get("predictor_dim", "predictor")
        predictor_b_dim = ctx.step_params.get("predictor_b_dim", "predictor_b")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(response, sample_dim, response_dim, label="varpart response")
        require_dims(first, sample_dim, predictor_dim, label="varpart X1")
        require_dims(second, sample_dim, predictor_b_dim, label="varpart X2")
        labels = response.labels[sample_dim]
        if set(first.labels[sample_dim]) != set(labels) or set(second.labels[sample_dim]) != set(labels):
            raise StepError("varpart: all three inputs must share the same sample labels")
        names = list(response.labels[sample_dim])
        y = reorder(response, sample_dim, response_dim)
        first_matrix = reorder(first, sample_dim, predictor_dim)
        second_matrix = reorder(second, sample_dim, predictor_b_dim)
        order_first = [first.labels[sample_dim][name] for name in names]
        order_second = [second.labels[sample_dim][name] for name in names]
        x1 = first_matrix[order_first]
        x2 = second_matrix[order_second]
        y = np.asarray(y, dtype=np.float64)[: len(names)]
        if not (np.all(np.isfinite(y)) and np.all(np.isfinite(x1)) and np.all(np.isfinite(x2))):
            raise StepError("varpart: inputs must be finite")
        if y.shape[0] < 3:
            raise StepError("varpart: need at least three samples")
        if x1.size == 0 or x2.size == 0:
            raise StepError("varpart: predictor tables must not be empty")
        y = y - y.mean(axis=0, keepdims=True)
        ss_total = float(np.sum(y * y))
        if ss_total <= 0.0:
            raise StepError("varpart: response is constant")
        x1 = _standardize(x1, "X1")
        x2 = _standardize(x2, "X2")
        union = np.hstack([x1, x2])
        r2_1, adj_1, rank_1 = _fit(y, x1, ss_total, "X1")
        r2_2, adj_2, rank_2 = _fit(y, x2, ss_total, "X2")
        r2_3, adj_3, rank_3 = _fit(y, union, ss_total, "X1+X2")
        shared = adj_1 + adj_2 - adj_3
        a = adj_3 - adj_2
        b = adj_3 - adj_1
        d = 1.0 - adj_3
        rows = ["a", "b", "c", "d", "X1", "X2", "union"]
        values = np.array([
            [a, np.nan, rank_3 - rank_2],
            [b, np.nan, rank_3 - rank_1],
            [shared, np.nan, 0.0],
            [d, np.nan, np.nan],
            [adj_1, r2_1, rank_1],
            [adj_2, r2_2, rank_2],
            [adj_3, r2_3, rank_3],
        ], dtype=np.float64)
        out = Form(
            data=values.astype(np.float32),
            dims=["fraction", "statistic"],
            labels={"fraction": {name: i for i, name in enumerate(rows)},
                    "statistic": {"adj_r2": 0, "r2": 1, "df": 2}},
            info={"missing_code": np.nan, "method": "vegan::varpart",
                  "n_samples": len(names),
                  "fract": {
                      "[a+c] = X1": {"r2": r2_1, "adj_r2": adj_1, "df": rank_1},
                      "[b+c] = X2": {"r2": r2_2, "adj_r2": adj_2, "df": rank_2},
                      "[a+b+c] = X1+X2": {"r2": r2_3, "adj_r2": adj_3, "df": rank_3},
                  },
                  "indfract": {"a": a, "b": b, "c": shared, "d": d},
                  "testable": {"a": bool(rank_3 > rank_2), "b": bool(rank_3 > rank_1),
                               "c": False, "d": False},
                  "ranks": [rank_1, rank_2, rank_3]},
        )
        ctx[out_name] = out
        self._export_data = {
            "a": a, "b": b, "c": shared, "d": d,
            "r2": [r2_1, r2_2, r2_3], "adj_r2": [adj_1, adj_2, adj_3],
            "df": [rank_1, rank_2, rank_3],
        }
        print(f"[{self.name}] [a]={a:.6g} [b]={b:.6g} [c]={shared:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
