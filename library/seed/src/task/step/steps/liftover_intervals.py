"""Lift BED-like intervals between assemblies with a UCSC chain file."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.files import FileArtifact

from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from ._liftover_utils import ChainIndex, chain_path, load_chain

_DEFAULTS = {
    "region_dim": "region",
    "field_dim": "field",
    "chrom_field": "chrom",
    "start_field": "chromStart",
    "end_field": "chromEnd",
    "strand_field": "strand",
    "min_mapq": 0,
    "output": "liftover_intervals",
}

_FIELDS = {
    "start": 0,
    "end": 1,
    "strand": 2,
    "mapped": 3,
}


def _labels(form, dim):
    return (form.labels or {}).get(dim) or {}


def _decode(form, field_dim, name, operator):
    labels = _labels(form, field_dim)
    if name not in labels:
        raise StepError(f"{operator}: column '{name}' is required")
    values = np.asarray(form.data[:, labels[name]])
    encoder = ((form.info or {}).get("encoders") or {}).get(field_dim, {}).get(name)
    inverse = getattr(encoder, "inverse", None)
    if inverse:
        return [str(inverse.get(int(value), value)) for value in values]
    decoded = []
    for value in values:
        if isinstance(value, (float, np.floating)) and float(value).is_integer():
            decoded.append(str(int(value)))
        else:
            text = str(value)
            decoded.append(text[:-2] if text.endswith(".0") else text)
    return decoded


def _numeric(form, field_dim, name, operator):
    labels = _labels(form, field_dim)
    if name not in labels:
        raise StepError(f"{operator}: column '{name}' is required")
    values = np.asarray(form.data[:, labels[name]], dtype=float)
    if np.any(~np.isfinite(values)):
        raise StepError(f"{operator}: column '{name}' is not finite")
    return values


class LiftoverIntervalsStep(Step):
    provider = "operon-core"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "liftover_intervals",
        "kind": "operator",
        "title": "liftOver intervals",
        "description": "Map BED intervals to another assembly with a UCSC chain file.",
        "category": "Genome",
        "icon": "Route",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "region_dim", "default": "region"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                },
                {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "chain"}},
                },
            ],
            "output": {"mode": "declare", "schema": {"kind": "file", "numeric": False, "ndim": 0, "dims": [], "info": {"representation": {"type": "string", "const": "bed"}}, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        total = 0
        for item in inputs:
            data = getattr(item, "data", None)
            if data is not None:
                total += int(np.asarray(data).nbytes)
        return (max(total, 8 * 1024 * 1024), 1024 * 1024)

    def run(self, ctx, inputs):
        params = dict(_DEFAULTS)
        params.update(ctx.step_params or {})
        operator = self.name or "liftover_intervals"
        out_name = str(params.get("output") or self.name or "liftover_intervals")

        intervals = inputs[0]
        if len(intervals.dims) != 2:
            raise StepError(f"{operator}: interval input must be two-dimensional")
        index = ChainIndex(load_chain(chain_path(inputs[1], operator)))

        chrom_values = _decode(intervals, params["field_dim"], params["chrom_field"], operator)
        starts = _numeric(intervals, params["field_dim"], params["start_field"], operator)
        ends = _numeric(intervals, params["field_dim"], params["end_field"], operator)
        strand_values = None
        if params["strand_field"] in _labels(intervals, params["field_dim"]):
            strand_values = _decode(intervals, params["field_dim"], params["strand_field"], operator)
        if starts.shape[0] == 0:
            raise StepError(f"{operator}: no intervals to lift")
        if np.any(starts < 0) or np.any(ends < starts):
            raise StepError(f"{operator}: intervals must satisfy 0 <= start <= end")

        n = starts.shape[0]
        data = np.zeros((n, 4), dtype=float)
        mapped_lines = []
        unmapped_lines = []
        row_labels = {}
        for i in range(n):
            chrom = chrom_values[i]
            start = int(round(starts[i]))
            end = int(round(ends[i]))
            label = f"{chrom}:{start}-{end}"
            if label in row_labels:
                label = f"{label}#{i}"
            row_labels[label] = i
            strand = strand_values[i] if strand_values is not None else "."
            try:
                result = index.map_interval(chrom, start, end)
            except ValueError as exc:
                raise StepError(f"{operator}: {exc}") from exc
            if result is None:
                data[i] = (-1.0, -1.0, 0.0, 0.0)
                unmapped_lines.append(f"{chrom}\t{start}\t{end}\t{label}\t0\t{strand}")
                continue
            target, t_start, t_end, target_strand = result
            data[i] = (float(t_start), float(t_end), 1.0 if target_strand == "+" else -1.0, 1.0)
            mapped_lines.append(
                f"{target}\t{t_start}\t{t_end}\t{label}\t0\t{target_strand}"
            )

        directory = output_directory(ctx, out_name)
        mapped_path = directory / f"{out_name}.mapped.bed"
        unmapped_path = directory / f"{out_name}.unmapped.bed"
        mapped_path.write_bytes(("\n".join(mapped_lines) + ("\n" if mapped_lines else "")).encode("utf-8"))
        unmapped_path.write_bytes(
            ("\n".join(unmapped_lines) + ("\n" if unmapped_lines else "")).encode("utf-8")
        )
        result_files = [
            result_file("mapped", str(mapped_path), "bed", "Intervals lifted to the target assembly"),
            result_file("unmapped", str(unmapped_path), "bed", "Intervals without a target location"),
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "bed",
            {"mapped": str(mapped_path), "unmapped": str(unmapped_path)},
            info={
                "source": "liftover_intervals",
                "n_intervals": n,
                "n_mapped": len(mapped_lines),
                "n_unmapped": len(unmapped_lines),
            },
        )

        self._export_data = {
            "n_intervals": n,
            "n_mapped": len(mapped_lines),
            "n_unmapped": len(unmapped_lines),
            "map_rate": (len(mapped_lines) / n) if n else 0.0,
            "mapped_file": str(mapped_path),
            "mapped_bytes": int(mapped_path.stat().st_size),
            "unmapped_file": str(unmapped_path),
            "unmapped_bytes": int(unmapped_path.stat().st_size),
            "result_files": result_files,
        }
        print(
            f"[liftover_intervals] {n} intervals, {len(mapped_lines)} mapped, "
            f"{len(unmapped_lines)} unmapped"
        )

    def export(self, ctx):
        return self._export_data
