"""Jaccard similarity and reciprocal coverage for two interval sets."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._interval_utils import interval_table, merge_intervals, overlap_bp

_STAT_LABELS = (
    "n_a",
    "n_b",
    "bp_a",
    "bp_b",
    "intersection_bp",
    "union_bp",
    "jaccard",
    "n_a_overlapping",
    "n_b_overlapping",
    "fraction_a_covered",
    "fraction_b_covered",
)


def _overlaps_any(starts, ends, query_starts, query_ends):
    """Count intervals overlapping at least one merged query interval."""
    count = 0
    j = 0
    n = len(query_starts)
    for start, end in zip(starts, ends):
        while j < n and query_ends[j] <= start:
            j += 1
        if j < n and query_starts[j] < end:
            count += 1
    return count


class IntervalJaccardStep(Step):
    """Compare two interval sets with Jaccard and reciprocal coverage."""

    provider = "operon-core"
    parameters_file = "interval_jaccard.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interval_jaccard",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Jaccard similarity of two interval sets",
        "description": (
            "Merge two BED interval sets, then report intersection and union "
            "bases, Jaccard similarity, the number of intervals overlapping the "
            "other set, and reciprocal covered fractions."
        ),
        "category": "Genome",
        "icon": "GitCompare",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "name": "set_a",
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "a_region_dim", "default": "region"},
                        {"param": "a_field_dim", "default": "field"},
                    ],
                },
                {
                    "name": "set_b",
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "b_region_dim", "default": "region"},
                        {"param": "b_field_dim", "default": "field"},
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
        "outputs": ["similarity"],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(getattr(item, "nbytes", 0) or 0 for item in inputs)
        return (max(size // 4, 8 * 1024 * 1024), 4 * 1024 * 1024)

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        out_name = params.get("output") or self.name
        a_regions, _, a_totals, _, a_starts, a_ends, _ = interval_table(
            inputs[0],
            params.get("a_region_dim", "region"),
            params.get("a_field_dim", "field"),
            params.get("a_chrom_field", "chrom"),
            params.get("a_start_field", "chromStart"),
            params.get("a_end_field", "chromEnd"),
            "interval_jaccard",
        )
        b_regions, _, b_totals, _, b_starts, b_ends, _ = interval_table(
            inputs[1],
            params.get("b_region_dim", "region"),
            params.get("b_field_dim", "field"),
            params.get("b_chrom_field", "chrom"),
            params.get("b_start_field", "chromStart"),
            params.get("b_end_field", "chromEnd"),
            "interval_jaccard",
        )

        chroms = sorted(set(a_regions) | set(b_regions))
        bp_a = bp_b = intersection = 0
        a_covered = b_covered = 0
        a_over = b_over = 0
        for chrom in chroms:
            a = a_regions.get(chrom)
            b = b_regions.get(chrom)
            a_merged = merge_intervals(a["starts"], a["ends"]) if a else (np.zeros(0, np.int64), np.zeros(0, np.int64))
            b_merged = merge_intervals(b["starts"], b["ends"]) if b else (np.zeros(0, np.int64), np.zeros(0, np.int64))
            bp_a += int(np.sum(a_merged[1] - a_merged[0]))
            bp_b += int(np.sum(b_merged[1] - b_merged[0]))
            intersection += overlap_bp(a_merged[0], a_merged[1], b_merged[0], b_merged[1])
            if a and len(b_merged[0]):
                a_covered += overlap_bp(a_merged[0], a_merged[1], b_merged[0], b_merged[1])
                a_over += _overlaps_any(a["starts"], a["ends"], b_merged[0], b_merged[1])
            if b and len(a_merged[0]):
                b_covered += overlap_bp(b_merged[0], b_merged[1], a_merged[0], a_merged[1])
                b_over += _overlaps_any(b["starts"], b["ends"], a_merged[0], a_merged[1])

        union = bp_a + bp_b - intersection
        jaccard = float(intersection) / float(union) if union else 0.0
        values = (
            float(len(a_starts)),
            float(len(b_starts)),
            float(bp_a),
            float(bp_b),
            float(intersection),
            float(union),
            jaccard,
            float(a_over),
            float(b_over),
            float(a_covered) / float(bp_a) if bp_a else 0.0,
            float(b_covered) / float(bp_b) if bp_b else 0.0,
        )
        data = np.asarray(values, dtype=float).reshape(-1, 1)
        labels = {name: i for i, name in enumerate(_STAT_LABELS)}
        out = Form(
            data=data,
            dims=["statistic", "value"],
            labels={"statistic": labels, "value": {"value": 0}},
            info={"intersection_bp": intersection, "union_bp": union},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "jaccard": jaccard,
            "intersection_bp": intersection,
            "union_bp": union,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
