"""Annotate BED intervals with genomic feature classes."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._interval_utils import interval_table, merge_intervals

_STAT_LABELS = ("class_index", "n_classes", "overlap_bp")


def annotate_intervals(regions, feature_regions, class_names, priority):
    """Return per-interval (priority class, class count, overlap bp)."""
    n_classes = len(class_names)
    result = {}
    for chrom, region in regions.items():
        starts, ends, order = region["starts"], region["ends"], region["order"]
        features = feature_regions.get(chrom)
        per_class = []
        if features:
            for class_index in range(n_classes):
                members = features["by_class"].get(class_index)
                if not members or len(members[0]) == 0:
                    per_class.append(None)
                    continue
                merged = merge_intervals(members[0], members[1])
                per_class.append(merged)
        else:
            per_class = [None] * n_classes
        cursors = [0] * n_classes
        for position in range(len(starts)):
            start, end = int(starts[position]), int(ends[position])
            hit = []
            for class_index in range(n_classes):
                merged = per_class[class_index]
                if merged is None:
                    continue
                fstarts, fends = merged
                cursor = cursors[class_index]
                while cursor < len(fstarts) and fends[cursor] <= start:
                    cursor += 1
                cursors[class_index] = cursor
                k = cursor
                covered = 0
                while k < len(fstarts) and fstarts[k] < end:
                    covered += max(0, min(end, int(fends[k])) - max(start, int(fstarts[k])))
                    k += 1
                if covered > 0:
                    hit.append((class_index, covered))
            chosen = n_classes
            chosen_bp = 0
            for candidate in priority:
                match = [covered for class_index, covered in hit if class_index == candidate]
                if match:
                    chosen = candidate
                    chosen_bp = match[0]
                    break
            result[int(order[position])] = (chosen, len(hit), chosen_bp)
    return result


class IntervalAnnotateStep(Step):
    """Assign each interval to the highest-priority overlapping feature class."""

    provider = "operon-core"
    parameters_file = "interval_annotate.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interval_annotate",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Annotate intervals by feature class",
        "description": (
            "Assign every BED interval to the highest-priority genomic feature "
            "class it overlaps (for example promoter before exon before "
            "intron), and report the number of classes and overlapped bases."
        ),
        "category": "Genome",
        "icon": "Tags",
        "contracts": {
            "version": 1,
            "inputs": [
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
        "outputs": ["annotation"],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(getattr(item, "nbytes", 0) or 0 for item in inputs)
        return (max(size // 4, 8 * 1024 * 1024), 4 * 1024 * 1024)

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        out_name = params.get("output") or self.name
        region_dim = params.get("interval_region_dim", "region")
        field_dim = params.get("interval_field_dim", "field")
        f_region = params.get("feature_region_dim", "region")
        f_field = params.get("feature_field_dim", "field")
        class_field = params.get("class_field", "name")
        names = [
            name.strip()
            for name in str(params.get("class_names", "promoter,utr5,cds,utr3,exon,intron")).split(",")
            if name.strip()
        ]
        priority = [
            name.strip()
            for name in str(params.get("priority", ",".join(names))).split(",")
            if name.strip()
        ]
        unknown = [name for name in priority if name not in names]
        if unknown:
            raise StepError(f"interval_annotate: priority classes not in class_names: {unknown}")
        priority_index = [names.index(name) for name in priority]

        regions, _, _, _, _, _, _ = interval_table(
            inputs[0], region_dim, field_dim,
            params.get("interval_chrom_field", "chrom"),
            params.get("interval_start_field", "chromStart"),
            params.get("interval_end_field", "chromEnd"),
            "interval_annotate",
        )
        (
            feature_regions,
            _feature_classes,
            _feature_totals,
            f_chrom_values,
            feature_starts,
            feature_ends,
            feature_class_values,
        ) = interval_table(
            inputs[1], f_region, f_field,
            params.get("feature_chrom_field", "chrom"),
            params.get("feature_start_field", "chromStart"),
            params.get("feature_end_field", "chromEnd"),
            "interval_annotate",
            class_field=class_field,
            class_names=names,
        )
        by_chrom = {}
        for chrom, start, end, class_index in zip(
            f_chrom_values, feature_starts, feature_ends, feature_class_values
        ):
            class_index = int(class_index)
            entry = by_chrom.setdefault(chrom, {"by_class": {}})
            if class_index < 0:
                continue
            entry["by_class"].setdefault(class_index, [[], []])
            entry["by_class"][class_index][0].append(int(start))
            entry["by_class"][class_index][1].append(int(end))
        for entry in by_chrom.values():
            for class_index, (starts, ends) in list(entry["by_class"].items()):
                order = np.argsort(starts, kind="stable")
                entry["by_class"][class_index] = (
                    np.asarray(starts, dtype=np.int64)[order],
                    np.asarray(ends, dtype=np.int64)[order],
                )

        table = annotate_intervals(regions, by_chrom, names, priority_index)
        data = np.zeros((len(table), len(_STAT_LABELS)), dtype=float)
        labels = {}
        for row, (original, (chosen, n_classes, overlap)) in enumerate(sorted(table.items())):
            data[row] = (float(chosen), float(n_classes), float(overlap))
            labels[str(original)] = row
        out = Form(
            data=data,
            dims=["interval", "statistic"],
            labels={"interval": labels, "statistic": {name: i for i, name in enumerate(_STAT_LABELS)}},
            info={"classes": list(names), "intergenic_index": len(names), "priority": list(priority)},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_intervals": len(table),
            "classes": names,
            "priority": priority,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))