"""Bio-environment matching between community and environmental distances."""
from __future__ import annotations

import itertools

import numpy as np
from scipy.stats import rankdata

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ecology_common import abundance, pairwise
from ._ext_common import reorder, require_dims


def _correlation(left, right, method):
    if method == "spearman":
        left = rankdata(left)
        right = rankdata(right)
    if np.std(left) == 0.0 or np.std(right) == 0.0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])


class BioenvStep(Step):
    provider = "operon-microbiome"
    parameters_file = "bioenv.BioenvStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "bioenv",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Bio-environment matching",
        "category": "Omics",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "taxon_dim", "default": "taxon"}],
                 "labels": [], "parallel": []},
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "env_dim", "default": "env"}],
                 "labels": [], "parallel": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26", "scipy>=1.11"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Bio-environment matching: for every subset size of the scaled "
            "environmental variables, report the largest Spearman or Pearson "
            "correlation between community distances and environmental "
            "distances, following vegan bioenv."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        community, env = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        env_dim = ctx.step_params.get("env_dim", "env")
        index = str(ctx.step_params.get("index", "bray"))
        method = str(ctx.step_params.get("method", "spearman"))
        upto = ctx.step_params.get("upto")
        out_name = ctx.step_params.get("output", self.name)
        if index not in ("bray", "euclidean", "manhattan"):
            raise StepError(f"bioenv: unsupported community index '{index}'")
        if method not in ("pearson", "spearman"):
            raise StepError(f"bioenv: unsupported correlation method '{method}'")
        require_dims(community, sample_dim, taxon_dim, label="bioenv community")
        require_dims(env, sample_dim, env_dim, label="bioenv environment")
        community_sample_labels = community.labels[sample_dim]
        env_sample_labels = env.labels[sample_dim]
        if set(env_sample_labels) != set(community_sample_labels):
            raise StepError(
                "bioenv: community and environment must share the same sample labels"
            )
        data, samples, taxa = abundance(community, sample_dim, taxon_dim, "bioenv")
        if len(samples) < 3:
            raise StepError("bioenv: need at least three samples")
        matrix = np.asarray(reorder(env, sample_dim, env_dim), dtype=np.float64)
        order = [env_sample_labels[name] for name in samples]
        matrix = matrix[order]
        if not np.all(np.isfinite(matrix)):
            raise StepError("bioenv: environment table must be finite")
        env_names = [name for name, _ in sorted(env.labels[env_dim].items(),
                                                key=lambda item: item[1])]
        if matrix.shape[1] == 0:
            raise StepError("bioenv: environment table has no variables")
        deviations = matrix.std(axis=0, ddof=1)
        keep = deviations > 0.0
        dropped = [name for name, flag in zip(env_names, keep) if not flag]
        matrix = matrix[:, keep]
        env_names = [name for name, flag in zip(env_names, keep) if flag]
        if matrix.shape[1] == 0:
            raise StepError("bioenv: all environment variables are constant")
        matrix = (matrix - matrix.mean(axis=0)) / matrix.std(axis=0, ddof=1)
        total = matrix.shape[1]
        limit = total if upto in (None, "") else int(upto)
        if limit < 1 or limit > total:
            raise StepError(f"bioenv: upto must be between 1 and {total}")
        distances = pairwise(data, index, "bioenv")
        upper = np.triu_indices(len(samples), 1)
        observed = distances[upper]
        models = []
        best_rho = -np.inf
        best_variables: list[str] = []
        best_size = 0
        for size in range(1, limit + 1):
            size_rho = -np.inf
            size_best: tuple[int, ...] = ()
            for combo in itertools.combinations(range(total), size):
                selected = pairwise(matrix[:, combo], "euclidean", "bioenv")
                rho = _correlation(observed, selected[upper], method)
                if np.isfinite(rho) and rho > size_rho:
                    size_rho = float(rho)
                    size_best = combo
            if not size_best:
                raise StepError(f"bioenv: no usable environmental subset of size {size}")
            names = [env_names[i] for i in size_best]
            models.append({"size": size, "variables": names, "rho": size_rho})
            if size_rho > best_rho:
                best_rho = size_rho
                best_variables = names
                best_size = size
        values = np.asarray([[model["rho"]] for model in models], dtype=np.float32)
        labels = [str(model["size"]) for model in models]
        out = Form(
            data=values,
            dims=["size", "statistic"],
            labels={"size": {name: i for i, name in enumerate(labels)},
                    "statistic": {"rho": 0}},
            info={"missing_code": np.nan, "method": "vegan::bioenv",
                  "index": index, "correlation": method,
                  "n_samples": len(samples), "n_taxa": len(taxa),
                  "n_env": total, "best_size": best_size,
                  "best_rho": float(best_rho),
                  "best_variables": best_variables,
                  "models": models, "dropped_constant": dropped},
        )
        ctx[out_name] = out
        self._export_data = {
            "best_size": best_size,
            "best_rho": float(best_rho),
            "best_variables": best_variables,
        }
        print(f"[{self.name}] best size={best_size} rho={best_rho:.6g} "
              f"variables={','.join(best_variables)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
