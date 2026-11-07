"""Vector error correction model (VECM)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._cointegration_common import variables_matrix


class VecmStep(Step):
    provider = 'operon-core'
    """Estimate a VECM and expose the Johansen trace/eigen diagnostics.

    The Johansen eigenvalues and trace statistics use the constant-in-model
    convention matching R ``urca::ca.jo(ecdet = "none")``.  Coefficients are
    reported on the same normalization as R: the first variable of each
    cointegrating relation is fixed to one.
    """
    parameters_file = 'vecm.VecmStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'vecm',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Vector error correction model',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Estimate a VECM and expose the Johansen trace/eigen diagnostics.'}


    def run(self, ctx: Context, inputs) -> None:
        import statsmodels.tsa.vector_ar.vecm as vecm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        rank = int(ctx.step_params.get("coint_rank", 1))
        k_ar_diff = int(ctx.step_params.get("k_ar_diff", 1))
        out_name = ctx.step_params.get("output", self.name)

        data, features, n = variables_matrix(
            inputs[0], sample_dim, feature_dim, self.name
        )
        k = len(features)
        if rank < 1 or rank >= k:
            raise StepError(
                f"{self.name}: coint_rank must be between 1 and {k - 1}"
            )
        if k_ar_diff < 1:
            raise StepError(f"{self.name}: k_ar_diff must be at least 1")
        if k_ar_diff >= n - 2:
            raise StepError(f"{self.name}: k_ar_diff must be less than n - 2")

        try:
            johansen = vecm.coint_johansen(data, 0, k_ar_diff)
            result = vecm.VECM(
                data,
                k_ar_diff=k_ar_diff,
                coint_rank=rank,
                deterministic="n",
            ).fit()
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: VECM fit failed: {exc}") from exc

        trace = np.asarray(johansen.trace_stat, dtype=np.float64)
        eigenvalues = np.asarray(johansen.eig, dtype=np.float64)
        beta = np.asarray(result.beta, dtype=np.float64)
        alpha = np.asarray(result.alpha, dtype=np.float64)
        llf = float(result.llf)
        if (
            trace.shape != (k,)
            or eigenvalues.shape != (k,)
            or beta.shape != (k, rank)
            or alpha.shape != (k, rank)
            or not np.isfinite(trace).all()
            or not np.isfinite(eigenvalues).all()
            or not np.isfinite(beta).all()
            or not np.isfinite(alpha).all()
            or not np.isfinite(llf)
        ):
            raise StepError(f"{self.name}: non-finite VECM result")

        terms: list[str] = []
        values: list[float] = []
        for i in range(k):
            terms.append(f"trace_r{i}")
            values.append(float(trace[i]))
            terms.append(f"eigen_r{i}")
            values.append(float(eigenvalues[i]))
        for j in range(rank):
            for i, feature in enumerate(features):
                terms.append(f"beta_r{j}_{feature}")
                values.append(float(beta[i, j]))
                terms.append(f"alpha_r{j}_{feature}")
                values.append(float(alpha[i, j]))

        rows = np.asarray(values, dtype=np.float64).reshape(-1, 1)
        form = Form(
            rows,
            ["term", "statistic"],
            {
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {"value": 0},
            },
            {
                "method": "VECM",
                "deterministic": "n",
                "coint_rank": rank,
                "k_ar_diff": k_ar_diff,
                "variables": features,
                "n": n,
                "llf": llf,
                "trace_stats": trace.tolist(),
                "eigenvalues": eigenvalues.tolist(),
                "beta": beta.tolist(),
                "alpha": alpha.tolist(),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export = {
            "variables": features,
            "coint_rank": rank,
            "k_ar_diff": k_ar_diff,
            "n": n,
            "llf": llf,
            "trace_stats": trace.tolist(),
            "eigenvalues": eigenvalues.tolist(),
            "beta": beta.tolist(),
            "alpha": alpha.tolist(),
        }
        print(
            f"[{self.name}] variables={k}, rank={rank}, "
            f"trace0={float(trace[0]):.4f}, llf={llf:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
