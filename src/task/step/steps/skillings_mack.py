"""Skillings-Mack rank test for incomplete block designs."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._block_rank_common import block_matrix, rank_blocks
from ._ext_common import make_form


class SkillingsMackTestStep(Step):
    """Skillings-Mack test for an arbitrary incomplete block design.

    Blocks may contain different numbers of treatments and cells may be
    missing. The covariance matrix is built from the pattern of blocks in
    which each pair of treatments is observed. The observation graph must
    connect all treatments; otherwise the statistic is not identified.
    """

    name = "skillings_mack"
    title = "Skillings-Mack test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("block_dim", "block"), param("treatment_dim", "treatment")],
        ),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
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
        y, blocks, treatments = block_matrix(
            form, block_dim, treatment_dim, "skillings_mack"
        )
        observed = np.isfinite(y)
        per_block = observed.sum(axis=1)
        per_treatment = observed.sum(axis=0)
        if np.any(per_block < 2):
            raise StepError("skillings_mack: every block needs at least two observed treatments")
        if np.any(per_treatment < 1):
            raise StepError("skillings_mack: every treatment needs at least one observation")
        b = len(blocks)
        g = len(treatments)
        if b < 2:
            raise StepError("skillings_mack: need at least two blocks")
        if g < 2:
            raise StepError("skillings_mack: need at least two treatments")

        ranks = rank_blocks(y)
        centered = np.zeros(g, dtype=np.float64)
        for row in range(b):
            columns = np.flatnonzero(observed[row])
            k = columns.size
            scale = np.sqrt(12.0 / (k + 1.0))
            centered[columns] += scale * (ranks[row, columns] - (k + 1.0) / 2.0)

        overlap = np.zeros((g, g), dtype=np.float64)
        for i in range(g - 1):
            for j in range(i + 1, g):
                count = float(np.sum(observed[:, i] & observed[:, j]))
                overlap[i, j] = count
                overlap[j, i] = count
        diagonal = overlap.sum(axis=1)
        covariance = -overlap
        np.fill_diagonal(covariance, diagonal)
        if np.linalg.matrix_rank(covariance) < g - 1:
            raise StepError(
                "skillings_mack: the observation pattern does not connect all treatments"
            )
        statistic = float(centered @ np.linalg.pinv(covariance) @ centered)
        df = float(g - 1)
        p_value = float(stats.chi2.sf(statistic, df))
        values = [
            ("statistic", statistic),
            ("df", df),
            ("p", p_value),
            ("n_blocks", float(b)),
            ("n_treatments", float(g)),
            ("n_observations", float(observed.sum())),
        ]
        ctx[ctx.step_params.get("output", self.name)] = make_form(
            [[value] for _, value in values],
            ["statistic", "value"],
            {
                "statistic": {name: i for i, (name, _) in enumerate(values)},
                "value": {"value": 0},
            },
            {"method": "Skillings-Mack", "covariance": "pairwise block overlap"},
        )
        self._export_data = {
            "statistic": statistic,
            "df": int(df),
            "p": p_value,
            "n_blocks": b,
            "n_treatments": g,
            "n_observations": int(observed.sum()),
        }
        print(
            f"[skillings_mack] {b} blocks x {g} treatments, "
            f"chi2={statistic:.4g}, p={p_value:.4g}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
