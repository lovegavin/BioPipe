"""Merge overlapping BED intervals per chromosome (bedtools merge style).

Input: Form from BedReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [region, field]
    labels field = BED column names (chrom, chromStart, chromEnd, ...)
    info   missing_code=NaN, encoders={field: {label: encoder}}

Only chrom, chromStart and chromEnd are read. Records are grouped
by chromosome, sorted by start, and consecutive intervals are merged
when the gap between them is at most ``min_overlap`` bases:

    gap = next.start - current.end
    merge when gap <= min_overlap

With min_overlap=0, overlapping and book-ended intervals (gap == 0)
are merged. Negative gaps (real overlap) are always merged.

Output:
    data   2D float32, shape (n_merged, 4)
    dims   [merged_region, statistic]
    statistic = [start, end, length, n_intervals]
    length = end - start (0-based half-open)
    info["chrom"]  axis-parallel, chromosome of each merged region

Params:
    region_dim  : name of the record axis (default "region")
    field_dim   : name of the field axis (default "field")
    chrom_field : name of the chrom column (default "chrom")
    start_field : name of the start column (default "chromStart")
    end_field   : name of the end column   (default "chromEnd")
    min_overlap : merge intervals whose gap is <= this value (default 0)
    output      : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.forms.metadata import project_metadata
from src.reader.readers._labels import unique_labels
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("start", "end", "length", "n_intervals")


class IntervalMergeStep(Step):
    """Merge overlapping BED intervals per chromosome."""
    provider = 'biopipe-core'
    parameters_file = 'interval_merge.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'interval_merge',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'interval_merge',
     'description': 'Merge overlapping BED intervals per chromosome.',
     'category': 'analysis',
     'icon': 'Unite',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'missing_code': {'type': ['number', 'null']},
                                        'encoders': {'type': 'object', 'optional': True}},
                               'dims': [{'param': 'region_dim', 'default': 'region'},
                                        {'param': 'field_dim', 'default': 'field'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        rec_dim = ctx.step_params.get("region_dim", "region")
        fld_dim = ctx.step_params.get("field_dim", "field")
        chrom_field = ctx.step_params.get("chrom_field", "chrom")
        start_field = ctx.step_params.get("start_field", "chromStart")
        end_field = ctx.step_params.get("end_field", "chromEnd")
        min_overlap = int(ctx.step_params.get("min_overlap", 0))
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != rec_dim or form.dims[1] != fld_dim:
            raise StepError(
                f"interval_merge: expected 2D [{rec_dim},{fld_dim}], "
                f"got {form.dims}"
            )
        if min_overlap < 0:
            raise StepError(
                f"interval_merge: min_overlap must be >= 0, got {min_overlap}"
            )

        fld_labels = form.labels.get(fld_dim, {})
        for required in (chrom_field, start_field, end_field):
            if required not in fld_labels:
                raise StepError(
                    f"interval_merge: field dim '{fld_dim}' has no "
                    f"'{required}' label. Available: {sorted(fld_labels)}"
                )

        encoders = form.info.get("encoders", {}).get(fld_dim, {})
        chrom_enc = encoders.get(chrom_field)
        if chrom_enc is None:
            raise StepError(
                f"interval_merge: '{chrom_field}' column is not encoded"
            )

        chrom_codes = form.data[:, fld_labels[chrom_field]]
        starts = form.data[:, fld_labels[start_field]].astype(np.float64)
        ends = form.data[:, fld_labels[end_field]].astype(np.float64)

        if np.any(~np.isfinite(starts)) or np.any(~np.isfinite(ends)):
            raise StepError("interval_merge: start/end columns contain NaN")
        if np.any(ends <= starts):
            raise StepError("interval_merge: end must be > start for every record")

        by_chrom: dict[str, list[tuple[float, float]]] = {}
        for i in range(form.data.shape[0]):
            name = chrom_enc.inverse[int(round(float(chrom_codes[i])))]
            by_chrom.setdefault(name, []).append((starts[i], ends[i]))

        merged_rows: list[list[float]] = []
        chrom_col: list[str] = []
        name_col: list[str] = []

        for chrom in sorted(by_chrom):
            records = sorted(by_chrom[chrom], key=lambda r: (r[0], r[1]))
            cur_s, cur_e = records[0]
            cur_n = 1
            for s, e in records[1:]:
                gap = s - cur_e
                if gap <= min_overlap:
                    if e > cur_e:
                        cur_e = e
                    cur_n += 1
                else:
                    merged_rows.append([
                        float(cur_s), float(cur_e),
                        float(cur_e - cur_s), float(cur_n),
                    ])
                    chrom_col.append(chrom)
                    name_col.append(f"{chrom}:{int(cur_s)}-{int(cur_e)}")
                    cur_s, cur_e, cur_n = s, e, 1
            merged_rows.append([
                float(cur_s), float(cur_e),
                float(cur_e - cur_s), float(cur_n),
            ])
            chrom_col.append(chrom)
            name_col.append(f"{chrom}:{int(cur_s)}-{int(cur_e)}")

        out_data = np.asarray(merged_rows, dtype=np.float32)

        unique_ids = unique_labels(name_col, "merged_region", "interval_merge")

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "merged_intervals"
        info["chrom"] = chrom_col

        axis_info = dict(axis_info)
        axis_info["merged_region"] = ["chrom"]

        out_form = Form(
            data=out_data,
            dims=["merged_region", "statistic"],
            labels={
                "merged_region": unique_ids,
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        n_input = int(form.data.shape[0])
        n_merged = len(merged_rows)
        self._export_data = {
            "region_dim": rec_dim,
            "field_dim": fld_dim,
            "min_overlap": min_overlap,
            "n_input_intervals": n_input,
            "n_merged_regions": n_merged,
            "n_removed_by_merge": n_input - n_merged,
            "n_chromosomes": len(by_chrom),
            "total_input_bp": float((ends - starts).sum()),
            "total_merged_bp": float(out_data[:, 2].sum()),
        }

        print(
            f"[interval_merge] {n_input} intervals -> {n_merged} merged "
            f"regions across {len(by_chrom)} chroms, min_overlap={min_overlap}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
