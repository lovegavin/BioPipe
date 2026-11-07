"""Assembly NGx/auN metrics."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._assembly_ngx_utils import au_n, aux, contig_lengths, n50_l50, ngx
from ._assembly_utils import contig_records


class AssemblyNgxMetricsStep(Step):
    id = "assembly_ngx_metrics"
    provider = "operon-core"
    parameters_file = "assembly_ngx_metrics.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_ngx_metrics",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Assembly NGx and auN metrics",
        "description": "Compute NGx/NAx thresholds, N50/L50 and area-under-the-Nx-curve metrics for a genome assembly.",
        "provider": "operon-core",
        "category": "Genome",
        "icon": "Ruler",
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes) if inputs else 0
        return max(size, 8 * 2**20), 2**20

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        out_name = str(params.get("output", self.name))
        records = contig_records(inputs[0], sequence_dim, position_dim, "assembly_ngx_metrics")
        lengths = contig_lengths(records)
        total = int(lengths.sum())
        try:
            genome_size = int(params.get("genome_size", 0))
        except (TypeError, ValueError) as exc:
            raise StepError("assembly_ngx_metrics: genome_size must be an integer") from exc
        if genome_size <= 0:
            genome_size = total
        percentages = []
        for token in str(params.get("x_values", "50,90")).replace(";", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                value = float(token)
            except ValueError as exc:
                raise StepError(f"assembly_ngx_metrics: invalid x value {token!r}") from exc
            if not 0 < value <= 100:
                raise StepError("assembly_ngx_metrics: x values must be in (0, 100]")
            percentages.append(value)
        if not percentages:
            percentages = [50.0, 90.0]
        n50, l50 = n50_l50(lengths, total)
        rows = [
            ("genome_size", float(genome_size)),
            ("total_length", float(total)),
            ("n_contigs", float(lengths.size)),
            ("n50", float(n50)),
            ("l50", float(l50)),
            ("auN", au_n(lengths, float(total))),
            ("auNG", au_n(lengths, float(genome_size))),
        ]
        for value in percentages:
            label = f"{value:g}"
            rows.append((f"NG{label}", float(ngx(lengths, genome_size, value))))
            rows.append((f"NA{label}", float(aux(lengths, total, value))))
        data = np.asarray([[value] for _, value in rows], dtype=np.float64)
        labels = {row: index for index, (row, _) in enumerate(rows)}
        out = Form(
            data,
            dims=["statistic", "value"],
            labels={"statistic": labels, "value": {"value": 0}},
            info={
                "genome_size": genome_size,
                "total_length": total,
                "n_contigs": int(lengths.size),
                "x_values": percentages,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "genome_size": genome_size,
            "total_length": total,
            "n_contigs": int(lengths.size),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
