"""Durbin rank test for a balanced incomplete block design."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._block_rank_common import block_matrix, rank_blocks
from ._ext_common import make_form


class DurbinTestStep(Step):
    provider = 'operon-core'
    """Durbin's rank sum test for a balanced incomplete block design.

    Each block contains the same number ``k`` of the ``t`` treatments, every
    treatment occurs in the same number ``r`` of blocks, and the design is
    incomplete (``k < t``). Missing cells are represented by NaN.
    """
    parameters_file = 'durbin_test.DurbinTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'durbin_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Durbin test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'block_dim', 'default': 'block'},
                                        {'param': 'treatment_dim', 'default': 'treatment'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['scipy>=1.11'],
     'dependency_imports': ['scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Durbin's rank sum test for a balanced incomplete block design."}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        block_dim = ctx.step_params.get("block_dim", "block")
        treatment_dim = ctx.step_params.get("treatment_dim", "treatment")
        y, blocks, treatments = block_matrix(
            form, block_dim, treatment_dim, "durbin_test"
        )
        observed = np.isfinite(y)
        per_block = observed.sum(axis=1)
        per_treatment = observed.sum(axis=0)
        if np.any(per_block < 2):
            raise StepError("durbin_test: every block needs at least two observed treatments")
        if np.any(per_treatment < 2):
            raise StepError("durbin_test: every treatment must occur in at least two blocks")
        block_counts = np.unique(per_block)
        treatment_counts = np.unique(per_treatment)
        if block_counts.size != 1 or treatment_counts.size != 1:
            raise StepError(
                "durbin_test: a balanced incomplete block design needs equal "
                "observed counts per block and per treatment"
            )
        k = int(block_counts[0])
        r = int(treatment_counts[0])
        b = len(blocks)
        t = len(treatments)
        if k >= t:
            raise StepError("durbin_test: the design must be incomplete (k < treatments)")
        if b < 2:
            raise StepError("durbin_test: need at least two blocks")

        ranks = rank_blocks(y)
        a_value = float(np.nansum(ranks**2))
        c_value = b * k * (k + 1.0) ** 2 / 4.0
        rank_sums = np.nansum(ranks, axis=0)
        d_value = float(np.sum(rank_sums**2) - r * c_value)
        denominator = a_value - c_value
        if denominator <= 0.0:
            raise StepError("durbin_test: degenerate rank sums (zero denominator)")
        statistic = float((t - 1.0) * d_value / denominator)
        df = float(t - 1)
        p_value = float(stats.chi2.sf(statistic, df))
        values = [
            ("statistic", statistic),
            ("df", df),
            ("p", p_value),
            ("n_blocks", float(b)),
            ("n_treatments", float(t)),
            ("n_per_block", float(k)),
            ("n_replicates", float(r)),
        ]
        ctx[ctx.step_params.get("output", self.name)] = make_form(
            [[value] for _, value in values],
            ["statistic", "value"],
            {
                "statistic": {name: i for i, (name, _) in enumerate(values)},
                "value": {"value": 0},
            },
            {"method": "Durbin", "design": "balanced incomplete block"},
        )
        self._export_data = {
            "statistic": statistic,
            "df": int(df),
            "p": p_value,
            "n_blocks": b,
            "n_treatments": t,
            "n_per_block": k,
            "n_replicates": r,
        }
        print(
            f"[durbin_test] {b} blocks x {t} treatments, "
            f"k={k}, chi2={statistic:.4g}, p={p_value:.4g}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
