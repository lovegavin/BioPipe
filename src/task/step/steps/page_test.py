"""Page test for ordered alternatives in a complete block design."""
from __future__ import annotations

import math
from itertools import permutations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import require_dims
from ._stats20_common import scalar_form


class PageTestStep(Step):
    """Page's L test for a monotone ordered alternative.

    The input is a complete ``[block, treatment]`` matrix with exactly one
    observation per block/treatment cell. Ranks are assigned within each
    block and ``L = sum(j * rank_sum_j)``. Small designs use the exact
    permutation distribution; larger designs use the normal approximation
    recommended by Page (1963).
    """

    name = "page_test"
    title = "Page test for ordered alternatives"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("block_dim", "block"), param("treatment_dim", "treatment")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "block_dim": {"type": "string", "default": "block"},
            "treatment_dim": {"type": "string", "default": "treatment"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        block_dim = ctx.step_params.get("block_dim", "block")
        treatment_dim = ctx.step_params.get("treatment_dim", "treatment")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, block_dim, treatment_dim, label="page_test")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(block_dim) == 1:
            data = data.T
        n_blocks, n_treatments = data.shape
        if n_blocks < 2 or n_treatments < 2:
            raise StepError("page_test: need at least two blocks and two treatments")
        if not np.all(np.isfinite(data)):
            raise StepError("page_test: all block/treatment cells must be finite")
        for row in data:
            if len(set(row.tolist())) != n_treatments:
                raise StepError("page_test: ties within a block are not supported")

        ranks = np.vstack([stats.rankdata(row, method="average") for row in data])
        rank_sums = ranks.sum(axis=0)
        l_value = float(np.dot(np.arange(1, n_treatments + 1), rank_sums))
        exact = n_treatments <= 8 and n_blocks <= 1000
        z_value = float("nan")
        if exact:
            block_probs = _page_block_distribution(n_treatments)
            distribution = np.array([1.0])
            for _ in range(n_blocks):
                distribution = np.convolve(distribution, block_probs)
            index = int(round(l_value))
            p_value = float(np.sum(distribution[index:]))
        else:
            mean = n_blocks * n_treatments * (n_treatments + 1) ** 2 / 4.0
            variance = n_blocks * n_treatments ** 2 * (n_treatments + 1) * (n_treatments ** 2 - 1) / 144.0
            if variance <= 0:
                raise StepError("page_test: invalid normal-approximation variance")
            z_value = float((l_value - mean) / math.sqrt(variance))
            p_value = float(stats.norm.sf(z_value))
        p_value = min(max(p_value, 0.0), 1.0)

        out = scalar_form(
            [l_value, p_value, z_value, float(n_blocks), float(n_treatments), float(exact)],
            ["L", "p", "z", "n_blocks", "n_treatments", "exact"],
            "page_test",
        )
        out.info.update({"alternative": "increasing treatment order", "method": "exact" if exact else "normal approximation"})
        ctx[out_name] = out
        self._export_data = {
            "L": l_value, "p": p_value, "z": z_value,
            "n_blocks": n_blocks, "n_treatments": n_treatments, "exact": bool(exact),
        }
        print(f"[page_test] L={l_value:g}, p={p_value:.6g}, exact={exact}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _page_block_distribution(k: int) -> np.ndarray:
    """Exact distribution of one block's weighted rank sum."""
    max_weight = k * (k + 1) * (2 * k + 1) // 6
    counts = np.zeros(max_weight + 1, dtype=np.float64)
    for perm in permutations(range(1, k + 1)):
        weight = sum((j + 1) * perm[j] for j in range(k))
        counts[weight] += 1.0
    return counts / math.factorial(k)
