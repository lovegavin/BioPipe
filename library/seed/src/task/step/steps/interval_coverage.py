"""Per-class coverage of genomic features by query intervals."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._interval_utils import coverage_bp, interval_table, merge_intervals

_STAT_LABELS = (
    "n_features",
    "feature_bp",
    "covered_bp",
    "covered_fraction",
    "n_covered_features",
)


class IntervalCoverageStep(Step):
    """Summarise how much of each feature class is covered by intervals."""

    provider = "operon-core"
    parameters_file = "interval_coverage.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interval_coverage",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Coverage of feature classes by intervals",
        "description": (
            "For every genomic feature class (promoter, exon, intron, ...) "
            "compute how many bases are covered by a set of intervals and the "
            "fraction of the class that is covered."
        ),
        "category": "Genome",
        "icon": "PieChart",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "name": "features",
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "feature_region_dim", "default": "region"},
                        {"param": "feature_field_dim", "default": "field"},
                    ],
                },
                {
                    "name": "intervals",
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "interval_region_dim", "default": "region"},
                        {"param": "interval_field_dim", "default": "field"},
                    ],
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 2,
        "outputs": ["coverage"],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(getattr(item, "nbytes", 0) or 0 for item in inputs)
        return (max(size // 4, 8 * 1024 * 1024), 4 * 1024 * 1024)

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        out_name = params.get("output") or self.name
        region_dim = params.get("feature_region_dim", "region")
        field_dim = params.get("feature_field_dim", "field")
        names = [
            name.strip()
            for name in str(params.get("class_names", "promoter,utr5,cds,utr3,exon,intron")).split(",")
            if name.strip()
        ]
        class_field = params.get("class_field", "name")

        (
            regions,
            _classes,
            _totals,
            chrom_values,
            starts,
            ends,
            class_values,
        ) = interval_table(
            inputs[0], region_dim, field_dim,
            params.get("feature_chrom_field", "chrom"),
            params.get("feature_start_field", "chromStart"),
            params.get("feature_end_field", "chromEnd"),
            "interval_coverage",
            class_field=class_field,
            class_names=names,
        )
        query_regions, _, _, _, _, _, _ = interval_table(
            inputs[1],
            params.get("interval_region_dim", "region"),
            params.get("interval_field_dim", "field"),
            params.get("interval_chrom_field", "chrom"),
            params.get("interval_start_field", "chromStart"),
            params.get("interval_end_field", "chromEnd"),
            "interval_coverage",
        )
        merged_queries = {}
        for chrom, region in query_regions.items():
            merged_queries[chrom] = merge_intervals(region["starts"], region["ends"])

        n_classes = len(names)
        feature_bp = np.zeros(n_classes, dtype=np.int64)
        covered_bp = np.zeros(n_classes, dtype=np.int64)
        n_features = np.zeros(n_classes, dtype=np.int64)
        n_covered = np.zeros(n_classes, dtype=np.int64)
        for chrom, start, end, class_index in zip(chrom_values, starts, ends, class_values):
            class_index = int(class_index)
            if class_index < 0:
                raise StepError(
                    "interval_coverage: every feature row needs a known class"
                )
            length = int(end - start)
            feature_bp[class_index] += length
            n_features[class_index] += 1
            query = merged_queries.get(chrom)
            if query is None or len(query[0]) == 0:
                continue
            covered = int(coverage_bp(np.asarray([start]), np.asarray([end]), query[0], query[1])[0])
            covered_bp[class_index] += covered
            if covered > 0:
                n_covered[class_index] += 1

        labels = {name: i for i, name in enumerate(names)}
        data = np.zeros((n_classes, len(_STAT_LABELS)), dtype=float)
        for i in range(n_classes):
            fraction = float(covered_bp[i]) / float(feature_bp[i]) if feature_bp[i] else 0.0
            data[i] = (
                float(n_features[i]),
                float(feature_bp[i]),
                float(covered_bp[i]),
                fraction,
                float(n_covered[i]),
            )
        out = Form(
            data=data,
            dims=["class", "statistic"],
            labels={"class": labels, "statistic": {name: i for i, name in enumerate(_STAT_LABELS)}},
            info={"classes": names},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_classes": n_classes,
            "covered_bp": int(covered_bp.sum()),
            "feature_bp": int(feature_bp.sum()),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
