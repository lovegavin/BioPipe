"""One-way MANOVA for several numeric responses."""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_values


def _statistics(eigs, df_h, df_e, test):
    p = len(eigs)
    q = df_h
    if test == "pillai":
        value = float(np.sum(eigs / (1.0 + eigs)))
        s = min(p, q)
        n = 0.5 * (df_e - p - 1)
        m = 0.5 * (abs(p - q) - 1)
        tmp1 = 2.0 * m + s + 1.0
        tmp2 = 2.0 * n + s + 1.0
        f_value = (tmp2 / tmp1 * value) / (s - value)
        num_df = s * tmp1
        den_df = s * tmp2
    elif test == "wilks":
        value = float(np.prod(1.0 / (1.0 + eigs)))
        tmp1 = df_e - 0.5 * (p - q + 1.0)
        tmp2 = (p * q - 2.0) / 4.0
        tmp3 = p * p + q * q - 5.0
        tmp3 = float(np.sqrt(((p * q) ** 2 - 4.0) / tmp3)) if tmp3 > 0 else 1.0
        f_value = ((value ** (-1.0 / tmp3) - 1.0)
                   * (tmp1 * tmp3 - 2.0 * tmp2) / p / q)
        num_df = p * q
        den_df = tmp1 * tmp3 - 2.0 * tmp2
    elif test == "hotelling_lawley":
        value = float(np.sum(eigs))
        m = 0.5 * (abs(p - q) - 1.0)
        n = 0.5 * (df_e - p - 1.0)
        s = min(p, q)
        tmp1 = 2.0 * m + s + 1.0
        tmp2 = 2.0 * (s * n + 1.0)
        f_value = tmp2 * value / s / s / tmp1
        num_df = s * tmp1
        den_df = tmp2
    elif test == "roy":
        value = float(np.max(eigs))
        tmp1 = float(max(p, q))
        tmp2 = df_e - tmp1 + q
        f_value = tmp2 * value / tmp1
        num_df = tmp1
        den_df = tmp2
    else:
        raise StepError(f"manova: unknown test {test!r}")
    p_value = float(sps.f.sf(f_value, num_df, den_df))
    return value, float(f_value), float(num_df), float(den_df), p_value


class ManovaStep(Step):
    provider = "operon-core"
    parameters_file = "manova.ManovaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "manova",
        "version": "1.0.0",
        "kind": "operator",
        "title": "One-way MANOVA",
        "category": "Statistics",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "response_dim", "default": "response"}],
                 "labels": [], "parallel": []},
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "group_dim", "default": "feature"}],
                 "labels": [], "parallel": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True,
                                  "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26", "scipy>=1.11"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "One-way MANOVA for one or more numeric responses with Pillai, "
            "Wilks, Hotelling-Lawley or Roy statistics, following "
            "R stats::summary.manova approximations."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        values, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        response_dim = ctx.step_params.get("response_dim", "response")
        group_dim = ctx.step_params.get("group_dim", "feature")
        group_label = ctx.step_params["group_label"]
        test = ctx.step_params.get("test", "pillai")
        out_name = ctx.step_params.get("output", self.name)

        if values.dims[0] != sample_dim or response_dim not in values.dims:
            raise StepError(
                f"manova: values must be [{sample_dim}, {response_dim}], "
                f"got {values.dims}"
            )
        if meta.dims[0] != sample_dim or group_dim not in meta.dims:
            raise StepError(
                f"manova: group table must be [{sample_dim}, {group_dim}], "
                f"got {meta.dims}"
            )
        names, groups = group_values(meta, sample_dim, group_label)
        values_labels = values.labels[sample_dim]
        common = [name for name in values_labels if name in set(names)]
        if len(common) < 8:
            raise StepError(f"manova: only {len(common)} shared samples")
        row_of = {name: i for i, name in enumerate(values_labels)}
        rows = [row_of[name] for name in common]
        raw = np.asarray(values.data, dtype=np.float64)[rows, :]
        if raw.ndim != 2:
            raise StepError("manova: values must be 2D")
        group_by_name = dict(zip(names, groups))
        labels = [group_by_name[name] for name in common]
        keep = np.all(np.isfinite(raw), axis=1) & np.array(
            [g is not None for g in labels], dtype=bool
        )
        raw = raw[keep]
        labels = [g for g, k in zip(labels, keep) if k]
        levels = sorted(set(labels))
        if len(levels) < 2:
            raise StepError("manova: need at least two groups")
        n, p = raw.shape
        counts = [labels.count(level) for level in levels]
        if min(counts) < 2:
            raise StepError(f"manova: every group needs >= 2 samples, got {counts}")
        df_h = len(levels) - 1
        df_e = n - len(levels)
        if df_e < 1 or p > df_e:
            raise StepError(
                f"manova: {p} responses with {df_e} error degrees of freedom"
            )
        grand = raw.mean(axis=0)
        h = np.zeros((p, p))
        e = np.zeros((p, p))
        for level in levels:
            block = raw[np.array([g == level for g in labels])]
            mean = block.mean(axis=0)
            diff = mean - grand
            h += block.shape[0] * np.outer(diff, diff)
            centered = block - mean
            e += centered.T @ centered
        if np.linalg.matrix_rank(e) < p:
            raise StepError("manova: residual covariance is singular")
        eigs = np.real(np.linalg.eigvals(np.linalg.solve(e, h)))
        eigs = np.sort(eigs)[::-1]
        value, f_value, num_df, den_df, p_value = _statistics(
            eigs, df_h, df_e, test
        )
        rows_out = ["test", "statistic", "approx_f", "num_df", "den_df",
                    "p_value"]
        data = np.array([[0.0], [value], [f_value], [num_df], [den_df],
                         [p_value]], dtype=np.float32)
        ctx[out_name] = Form(
            data=data,
            dims=["statistic", "value"],
            labels={"statistic": {name: i for i, name in enumerate(rows_out)},
                    "value": {"value": 0}},
            info={"missing_code": np.nan, "test": test,
                  "n_samples": int(n), "n_groups": int(len(levels)),
                  "n_responses": int(p), "groups": list(map(str, levels))},
        )
        self._export_data = {
            "test": test,
            "statistic": value,
            "approx_f": f_value,
            "num_df": num_df,
            "den_df": den_df,
            "p_value": p_value,
            "n_samples": int(n),
            "n_groups": int(len(levels)),
            "groups": list(map(str, levels)),
        }
        print(f"[{self.name}] {test} F={f_value:.4f} p={p_value:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
