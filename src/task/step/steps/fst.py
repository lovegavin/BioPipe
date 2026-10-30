"""Hudson's Fst from biallelic genotype dosages and population labels."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_values, labels_in_order, make_form, reorder


class FstStep(Step):
    name = "fst"
    title = "Fst"
    category = "Genetics"
    builtin_package = "biopipe-genetics"
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("variant_dim", "variant"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
                                                     "info": {"missing_code": {"type": ["number", "null"]}}}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "variant_dim": {"type": "string", "default": "variant"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "group_a": {"type": ["string", "number"]},
            "group_b": {"type": ["string", "number"]},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        geno, meta = inputs
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label = ctx.step_params["group_label"]
        ga, gb = ctx.step_params["group_a"], ctx.step_params["group_b"]
        out_name = ctx.step_params.get("output", self.name)
        X = reorder(geno, variant_dim, sample_dim).astype(np.float64)
        variants = labels_in_order(geno, variant_dim)
        samples = labels_in_order(geno, sample_dim)
        meta_samples, groups = group_values(meta, sample_dim, label)
        mpos = {name: i for i, name in enumerate(meta_samples)}
        def same(value, target):
            try:
                return float(value) == float(target)
            except (TypeError, ValueError):
                return str(value) == str(target)
        ia = [i for i, name in enumerate(samples) if name in mpos and same(groups[mpos[name]], ga)]
        ib = [i for i, name in enumerate(samples) if name in mpos and same(groups[mpos[name]], gb)]
        if len(ia) < 2 or len(ib) < 2:
            raise StepError("fst needs at least two genotyped samples in each group")
        rows = []
        for j in range(X.shape[0]):
            va = X[j, ia]; vb = X[j, ib]
            va = va[np.isfinite(va)]; vb = vb[np.isfinite(vb)]
            if len(va) < 2 or len(vb) < 2:
                rows.append([np.nan, len(va), len(vb), np.nan, np.nan]); continue
            p1 = float(np.mean(va) / 2.0); p2 = float(np.mean(vb) / 2.0)
            n1, n2 = len(va), len(vb)
            num = (p1 - p2) ** 2 - p1 * (1 - p1) / (n1 - 1) - p2 * (1 - p2) / (n2 - 1)
            den = p1 * (1 - p2) + p2 * (1 - p1)
            fst = num / den if den > 0 else np.nan
            rows.append([float(fst), n1, n2, p1, p2])
        out = make_form(rows, [variant_dim, "statistic"],
                        {variant_dim: {name: i for i, name in enumerate(variants)},
                         "statistic": {"fst": 0, "n_a": 1, "n_b": 2, "p_a": 3, "p_b": 4}})
        ctx[out_name] = out
        self._export_data = {"n_variants": len(variants), "group_a": ga, "group_b": gb,
                             "n_a": len(ia), "n_b": len(ib), "mean_fst": float(np.nanmean(out.data[:, 0]))}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
