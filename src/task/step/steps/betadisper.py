"""Multivariate homogeneity of group dispersions (betadisper)."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_values
from ._stats20_common import distance


class BetadisperStep(Step):
    """Distance-to-centroid dispersion per group, with one-way ANOVA."""

    name = "betadisper"
    title = "Beta dispersion"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("sample_b_dim", "sample_b")],
        ),
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("group_dim", "feature")],
        ),
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
            "sample_b_dim": {"type": "string", "default": "sample_b"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        dist_form, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]

        D, samples = distance(dist_form, sample_dim, sample_b_dim, self.name)
        meta_samples, values = group_values(meta, group_dim, group_label)
        meta_pos = {name: i for i, name in enumerate(meta_samples)}
        keep = [i for i, name in enumerate(samples) if name in meta_pos]
        if len(keep) < 4:
            raise StepError(f"{self.name}: only {len(keep)} shared samples")
        D = D[np.ix_(keep, keep)]
        kept_samples = [samples[i] for i in keep]
        raw_groups = [values[meta_pos[name]] for name in kept_samples]
        valid = [g is not None and str(g) != "" and str(g).lower() != "nan" for g in raw_groups]
        if sum(valid) < 4:
            raise StepError(f"{self.name}: fewer than four samples with a group")
        idx = [i for i, ok in enumerate(valid) if ok]
        D = D[np.ix_(idx, idx)]
        kept_samples = [kept_samples[i] for i in idx]
        labels = [str(raw_groups[i]) for i in idx]
        groups = sorted(set(labels))
        if len(groups) < 2:
            raise StepError(f"{self.name}: need at least two groups")
        codes = np.asarray([groups.index(value) for value in labels], dtype=np.int64)
        counts = np.bincount(codes, minlength=len(groups))
        if len(labels) <= len(groups):
            raise StepError(f"{self.name}: need more samples than groups")

        n = len(D)
        G = -0.5 * D**2
        G = G - G.mean(axis=0, keepdims=True) - G.mean(axis=1, keepdims=True) + G.mean()
        eigvals, eigvecs = np.linalg.eigh(G)
        order = np.argsort(eigvals)[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]
        threshold = max(1e-9, float(eigvals[0]) * 1e-12 if len(eigvals) else 0.0)
        positive = eigvals > threshold
        if not positive.any():
            raise StepError(f"{self.name}: no positive PCoA eigenvalues")
        coords = eigvecs[:, positive] * np.sqrt(eigvals[positive])

        centroids = np.vstack([coords[codes == g].mean(axis=0) for g in range(len(groups))])
        distances = np.linalg.norm(coords - centroids[codes], axis=1)
        group_means = np.asarray([distances[codes == g].mean() for g in range(len(groups))])

        grand = float(distances.mean())
        ss_between = float(sum(counts[g] * (group_means[g] - grand) ** 2 for g in range(len(groups))))
        ss_within = float(sum(((distances[codes == g] - group_means[g]) ** 2).sum() for g in range(len(groups))))
        df_between = len(groups) - 1
        df_within = n - len(groups)
        if ss_within <= 0.0:
            f_value = float("inf") if ss_between > 0 else float("nan")
            p_value = 0.0 if ss_between > 0 else float("nan")
        else:
            f_value = (ss_between / df_between) / (ss_within / df_within)
            p_value = float(stats.f.sf(f_value, df_between, df_within))

        data = np.column_stack([distances, codes.astype(float)])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data,
            dims=["sample", "statistic"],
            labels={
                "sample": {name: i for i, name in enumerate(kept_samples)},
                "statistic": {"distance": 0, "group_code": 1},
            },
            info={
                "group_labels": groups,
                "group_means": {g: float(group_means[i]) for i, g in enumerate(groups)},
                "group_sizes": {g: int(counts[i]) for i, g in enumerate(groups)},
                "F": float(f_value),
                "p": float(p_value),
                "df_between": int(df_between),
                "df_within": int(df_within),
                "n": int(n),
                "type": "centroid",
            },
        )
        self._export = {
            "samples": kept_samples,
            "distances": distances.tolist(),
            "groups": labels,
            "group_means": {g: float(group_means[i]) for i, g in enumerate(groups)},
            "centroids": centroids.tolist(),
            "eigenvalues": eigvals[positive].tolist(),
            "F": float(f_value),
            "p": float(p_value),
            "df_between": int(df_between),
            "df_within": int(df_within),
        }
        print(f"[{self.name}] n={n}, groups={len(groups)}, F={f_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
