"""Distance-decay curve from a long-form Hi-C contact table."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from . import _hic_utils as hic

_FIELDS = ["distance_start", "distance_end", "n_contacts", "n_pairs", "mean_count", "fraction"]


class HicDistanceDecayStep(Step):
    provider = "biopipe-core"
    parameters_file = "hic_distance_decay.parameters.json"
    definition = {
        "protocol_version": 3,
        "id": "hic_distance_decay",
        "version": "1.0.0",
        "kind": "operator",
        "title": "hic_distance_decay",
        "description": "Aggregate contact counts by genomic distance into a decay curve.",
        "category": "Genome",
        "icon": "TrendingUp",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "form", "numeric": True, "ndim": 2,
                 "dims": [{"param": "contact_dim", "default": "contact"}, {"param": "field_dim", "default": "field"}],
                 "labels": [],
                 "info_open": True},
            ],
            "output": {"mode": "declare", "schema": {
                "kind": "form", "numeric": True, "ndim": 2,
                "dims": [{"param": "distance_dim", "default": "distance_bin"}, {"param": "statistic_dim", "default": "statistic"}],
                "labels": {"distance_bin": [], "statistic": ["distance_start", "distance_end", "n_contacts", "n_pairs", "mean_count", "fraction"]},
                "info_open": True,
            }},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 64 * 1024 * 1024, 0

    def run(self, ctx, input_forms):
        params = ctx.step_params
        out_name = params.get("output", "decay")
        form = input_forms[0]
        field_dim = str(params.get("field_dim", "field"))
        contact_dim = str(params.get("contact_dim", "contact"))
        names = form.labels.get(field_dim) if isinstance(form.labels, dict) else None
        if not names:
            raise StepError("hic_distance_decay: contact table has no field labels")
        index = {name: position for name, position in names.items()} if isinstance(names, dict) else {name: i for i, name in enumerate(names)}
        for required in ("start1", "start2", "count"):
            if required not in index:
                raise StepError(f"hic_distance_decay: contact table is missing the {required!r} column")
        rows = []
        for row in range(form.data.shape[0]):
            start1 = float(form.data[row, index["start1"]])
            start2 = float(form.data[row, index["start2"]])
            count = float(form.data[row, index["count"]])
            rows.append(("", start1, start2, count))
        table, total = hic.decay_table(rows, int(params.get("n_bins", 20)), int(params.get("max_distance", 0)))
        data = np.asarray([[row[1], row[2], row[3], row[4], row[5], row[6]] for row in table], dtype=np.float64)
        labels = {row[0]: position for position, row in enumerate(table)}
        info = {
            "distance_dim": "distance_bin",
            "statistic_dim": "statistic",
            "n_bins": len(table),
            "total_pairs": total,
            "max_distance": float(params.get("max_distance", 0)) or float(max(row[2] for row in table)),
        }
        out = Form(data, dims=["distance_bin", "statistic"],
                   labels={"distance_bin": labels, "statistic": {name: position for position, name in enumerate(_FIELDS)}},
                   info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_bins": len(table), "total_pairs": total}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
