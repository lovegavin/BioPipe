"""Trimmed mean of M-values (TMM) normalization.

This is an independent Python implementation of the TMM method from
edgeR. Counts are scaled by effective library sizes

    effective_library_size = library_size * norm_factor

and converted to counts per ``target_sum``. The implementation follows
edgeR's reference-sample selection, trimmed log-ratio mean and optional
inverse-variance weighting, but is not a wrapper around R.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._ext_common import labels_in_order, reorder


class TmmNormalizeStep(Step):
    provider = 'operon-expression'
    """Normalize a count matrix with edgeR-style TMM factors."""
    parameters_file = 'tmm_normalize.TmmNormalizeStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'tmm_normalize',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'TMM normalization',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'transform', 'representation': 'tmm_normalize'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Normalize a count matrix with edgeR-style TMM factors.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        target_sum = float(ctx.step_params.get("target_sum", 1e6))
        logratio_trim = float(ctx.step_params.get("logratio_trim", 0.3))
        sum_trim = float(ctx.step_params.get("sum_trim", 0.05))
        do_weighting = bool(ctx.step_params.get("do_weighting", True))
        out_name = ctx.step_params.get("output", self.name)

        if not (0 <= logratio_trim < 0.5):
            raise StepError("tmm_normalize: logratio_trim must be in [0, 0.5)")
        if not (0 <= sum_trim < 0.5):
            raise StepError("tmm_normalize: sum_trim must be in [0, 0.5)")
        if target_sum <= 0:
            raise StepError("tmm_normalize: target_sum must be > 0")

        data = reorder(form, feature_dim, sample_dim).astype(np.float64)
        if not np.isfinite(data).all():
            raise StepError("tmm_normalize: counts must be complete (no NaN/inf)")
        if np.any(data < 0):
            raise StepError("tmm_normalize: counts must be non-negative")
        lib_sizes = data.sum(axis=0)
        if np.any(lib_sizes <= 0):
            bad = np.where(lib_sizes <= 0)[0]
            raise StepError(
                f"tmm_normalize: {len(bad)} sample(s) have zero total count "
                f"(positions {bad.tolist()[:5]})"
            )

        # edgeR chooses the reference from the 75th percentile of each
        # library-size-scaled sample, unless those values are all zero.
        f75 = np.quantile(data, 0.75, axis=0) / lib_sizes
        if np.median(f75) < 1e-20:
            ref = int(np.argmax(np.sqrt(data).sum(axis=0)))
        else:
            ref = int(np.argmin(np.abs(f75 - np.mean(f75))))

        factors = np.asarray([
            _calc_factor_tmm(
                data[:, i], data[:, ref], lib_sizes[i], lib_sizes[ref],
                logratio_trim, sum_trim, do_weighting,
            )
            for i in range(data.shape[1])
        ], dtype=np.float64)
        factors = factors / np.exp(np.mean(np.log(factors)))
        size_factors = lib_sizes * factors / target_sum
        normalized = data / size_factors[None, :]

        samples = labels_in_order(form, sample_dim)
        pos = {name: i for i, name in enumerate(samples)}
        info = dict(form.info)
        info.update(missing_code=np.nan, representation="tmm_normalize")
        ctx[out_name] = Form(
            data=normalized.astype(np.float32),
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=info,
            axis_info={k: dict(v) for k, v in form.axis_info.items()},
        )
        self._export_data = {
            "method": "TMM",
            "reference_sample": samples[ref],
            "target_sum": target_sum,
            "logratio_trim": logratio_trim,
            "sum_trim": sum_trim,
            "do_weighting": do_weighting,
            "library_sizes": {s: float(lib_sizes[pos[s]]) for s in samples},
            "norm_factors": {s: float(factors[pos[s]]) for s in samples},
            "effective_library_sizes": {
                s: float(lib_sizes[pos[s]] * factors[pos[s]]) for s in samples
            },
            "n_features": int(data.shape[0]),
            "n_samples": int(data.shape[1]),
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": "TMM",
            "reference_sample": samples[ref],
            "n_samples": int(data.shape[1]),
        }
        print(
            f"[tmm_normalize] n_samples={data.shape[1]} ref='{samples[ref]}' "
            f"factors [{factors.min():.4g}, {factors.max():.4g}]"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _calc_factor_tmm(obs, ref, lib_obs, lib_ref, logratio_trim, sum_trim,
                     do_weighting):
    """Port of edgeR's .calcFactorTMM for one sample against a reference."""
    obs = np.asarray(obs, dtype=np.float64)
    ref = np.asarray(ref, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_r = np.log2((obs / lib_obs) / (ref / lib_ref))
        abs_e = (np.log2(obs / lib_obs) + np.log2(ref / lib_ref)) / 2.0
        var = (lib_obs - obs) / lib_obs / obs + (lib_ref - ref) / lib_ref / ref
    finite = np.isfinite(log_r) & np.isfinite(abs_e)
    log_r = log_r[finite]
    abs_e = abs_e[finite]
    var = var[finite]
    if log_r.size == 0 or np.max(np.abs(log_r)) < 1e-6:
        return 1.0

    n = log_r.size
    lo_l = int(np.floor(n * logratio_trim)) + 1
    hi_l = n + 1 - lo_l
    lo_s = int(np.floor(n * sum_trim)) + 1
    hi_s = n + 1 - lo_s
    rank_l = stats.rankdata(log_r, method="average")
    rank_s = stats.rankdata(abs_e, method="average")
    keep = ((rank_l >= lo_l) & (rank_l <= hi_l)
            & (rank_s >= lo_s) & (rank_s <= hi_s))
    if do_weighting:
        f = np.sum(log_r[keep] / var[keep]) / np.sum(1.0 / var[keep])
    else:
        f = float(np.mean(log_r[keep]))
    if not np.isfinite(f):
        f = 0.0
    return float(2.0 ** f)
