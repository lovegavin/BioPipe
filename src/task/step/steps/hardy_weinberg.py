"""Exact Hardy-Weinberg equilibrium test for biallelic genotypes."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = {
    "n": 0,
    "alt_freq": 1,
    "obs_het": 2,
    "exp_het": 3,
    "fis": 4,
    "exact_p": 5,
}


def _exact_hwe(aa: int, ab: int, bb: int) -> float:
    """Two-sided exact HWE p-value conditional on the allele count.

    This is the Wigginton et al. (2005) recursion, with the same
    "less or equally likely" p-value as R ``HardyWeinberg::HWExact``.
    """
    n = aa + ab + bb
    if n <= 0:
        raise StepError("hardy_weinberg: genotype counts must be positive")
    rare = 2 * min(aa, bb) + ab
    if rare <= 0:
        return 1.0
    observed = ab
    current = int(round(rare * (2 * n - rare) / (2.0 * n)))
    if current > rare:
        current = rare
    if current % 2 != rare % 2:
        current -= 1
    if current < 0:
        current = 0
    probs = [0.0] * (rare + 1)
    probs[current] = 1.0
    for h in range(current, rare, 2):
        probs[h + 2] = (
            probs[h]
            * (rare - h)
            * (2 * n - rare - h)
            / ((h + 2) * (h + 1))
        )
    for h in range(current, 1, -2):
        probs[h - 2] = (
            probs[h]
            * h
            * (h - 1)
            / ((rare - h + 2) * (2 * n - rare - h + 2))
        )
    total = sum(probs)
    if not np.isfinite(total) or total <= 0:
        raise StepError("hardy_weinberg: numerical failure in exact test")
    probs = [value / total for value in probs]
    cutoff = probs[observed]
    p_value = sum(
        value
        for h, value in enumerate(probs)
        if h % 2 == rare % 2 and value <= cutoff
    )
    return float(min(1.0, max(0.0, p_value)))


class HardyWeinbergStep(Step):
    """Exact and descriptive Hardy-Weinberg statistics for biallelic variants."""

    name = "hardy_weinberg"
    title = "Hardy-Weinberg equilibrium"
    category = "Omics"
    builtin_package = "biopipe-genetics"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("variant_dim", "variant"), param("feature_dim", "feature")],
        )
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
            "variant_dim": {"type": "string", "default": "variant"},
            "feature_dim": {"type": "string", "default": "feature"},
            "aa_label": {"type": "string", "default": "AA"},
            "ab_label": {"type": "string", "default": "AB"},
            "bb_label": {"type": "string", "default": "BB"},
            "output": {"type": "string"},
        },
        "required": [],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        labels = [
            ctx.step_params.get("aa_label", "AA"),
            ctx.step_params.get("ab_label", "AB"),
            ctx.step_params.get("bb_label", "BB"),
        ]
        out_name = ctx.step_params.get("output", self.name)
        if len(set(labels)) != 3:
            raise StepError(f"{self.name}: genotype labels must be distinct")

        frame = table_frame(inputs[0], variant_dim, feature_dim, self.name)
        for name in labels:
            if name not in frame.columns:
                raise StepError(f"{self.name}: genotype column {name!r} not found")
        counts = [numeric_column(frame, name, self.name) for name in labels]
        for name, values in zip(labels, counts):
            if not np.all(np.isfinite(values)):
                raise StepError(f"{self.name}: genotype column {name!r} has missing values")
            if np.any(values < 0) or not np.allclose(values, np.round(values)):
                raise StepError(f"{self.name}: genotype column {name!r} must contain nonnegative integers")
        counts = [values.astype(np.int64) for values in counts]
        if np.any(counts[0] + counts[1] + counts[2] == 0):
            raise StepError(f"{self.name}: each variant needs at least one genotype")

        variants = [str(value) for value in frame["__sample__"].tolist()]
        rows = []
        mono = 0
        for i, variant in enumerate(variants):
            aa, ab, bb = (int(values[i]) for values in counts)
            n = aa + ab + bb
            alt = (2 * bb + ab) / (2.0 * n)
            obs = ab / n
            exp = 2.0 * alt * (1.0 - alt)
            fis = 1.0 - obs / exp if exp > 0 else 0.0
            p_value = _exact_hwe(aa, ab, bb)
            mono += int(alt in (0.0, 1.0))
            rows.append([float(n), float(alt), float(obs), float(exp), float(fis), float(p_value)])

        block = np.asarray(rows, dtype=np.float32)
        ctx[out_name] = Form(
            data=block,
            dims=["variant", "statistic"],
            labels={
                "variant": {name: i for i, name in enumerate(variants)},
                "statistic": dict(_STATISTICS),
            },
            info={
                "method": "exact conditional HWE",
                "n_variants": len(variants),
                "monomorphic": mono,
                "labels": {"AA": labels[0], "AB": labels[1], "BB": labels[2]},
            },
        )
        self._export = {
            "variants": variants,
            "n": [int(row[0]) for row in rows],
            "alt_freq": [float(row[1]) for row in rows],
            "obs_het": [float(row[2]) for row in rows],
            "exp_het": [float(row[3]) for row in rows],
            "fis": [float(row[4]) for row in rows],
            "exact_p": [float(row[5]) for row in rows],
        }
        print(f"[{self.name}] variants={len(variants)}, monomorphic={mono}")

    def export(self, ctx: Context) -> dict:
        return self._export
