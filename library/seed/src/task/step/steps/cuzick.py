"""Cuzick's test for an ordered trend across groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._order_rank_common import align_ordered, finite_groups


class CuzickTestStep(Step):
    """Rank-based trend test with user-supplied or default group scores.

    The statistic is ``T = sum(R_i * l_i)`` over the average rank sum ``R_i``
    of each group and its score ``l_i``. Ties are handled with their average
    ranks, which gives the same variance as ``PMCMRplus::cuzickTest`` when no
    ties are present and a tie-corrected variance otherwise.
    """

    provider = 'operon-core'

    parameters_file = 'cuzick.CuzickTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cuzick',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cuzick's trend test",
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'group_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Rank-based test for a monotone trend across ordered groups.'}

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        continuity = bool(ctx.step_params.get("continuity", False))

        values, features, order, indices = align_ordered(
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            group_label,
            ctx.step_params.get("group_order"),
            "cuzick",
        )
        groups = len(order)
        raw_scores = ctx.step_params.get("scores")
        if raw_scores is None:
            scores = np.arange(1.0, groups + 1.0)
        else:
            scores = np.asarray(raw_scores, dtype=np.float64)
            if scores.size != groups:
                raise StepError(
                    f"cuzick: scores has {scores.size} values but there are {groups} groups"
                )
            if not np.isfinite(scores).all():
                raise StepError("cuzick: scores must be finite")
        sizes = np.asarray([indices[group].size for group in order], dtype=np.float64)
        weight = np.sum(sizes * scores ** 2) - float(np.sum(sizes * scores)) ** 2 / float(sizes.sum())

        rows = []
        kept = []
        for column, feature in enumerate(features):
            finite = finite_groups(values[:, column], indices, order, "cuzick")
            if finite is None:
                continue
            flat = np.concatenate(finite)
            n = float(flat.size)
            ranks = stats.rankdata(flat, method="average")
            starts = np.cumsum([0] + [int(group.size) for group in finite[:-1]])
            rank_sums = np.asarray(
                [ranks[start : start + int(size)].sum() for start, size in zip(starts, [group.size for group in finite])],
                dtype=np.float64,
            )
            statistic = float(np.sum(rank_sums * scores))
            total = float(np.sum(sizes * scores))
            expected = total * (n + 1.0) / 2.0
            spread = float(np.sum((ranks - (n + 1.0) / 2.0) ** 2))
            variance = weight * spread / (n - 1.0)
            if not np.isfinite(variance) or variance <= 0.0:
                raise StepError("cuzick: variance is zero; values may be constant")
            adjusted = statistic
            if continuity:
                adjusted = adjusted + 0.5 if adjusted < expected else adjusted - 0.5
            z_value = (adjusted - expected) / np.sqrt(variance)
            if alternative == "greater":
                p_value = float(stats.norm.sf(z_value))
            elif alternative == "less":
                p_value = float(stats.norm.cdf(z_value))
            else:
                p_value = float(2.0 * stats.norm.sf(abs(z_value)))
            rows.append([statistic, z_value, p_value, n, float(groups)])
            kept.append(feature)

        if not rows:
            raise StepError("cuzick: no feature had enough finite observations per group")
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: index for index, name in enumerate(kept)},
                "statistic": {"T": 0, "z": 1, "p": 2, "n": 3, "n_groups": 4},
            },
            info={
                "missing_code": np.nan,
                "method": "Cuzick",
                "alternative": alternative,
                "group_order": order,
                "scores": [float(value) for value in scores],
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": groups,
            "groups": order,
            "alternative": alternative,
        }
        print(f"[cuzick] {len(kept)} features, {groups} groups")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
