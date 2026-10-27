"""Per-chromosome interval statistics for any BED-like Form.

Input: Form from BedReader (or any form with chrom/start/end columns).

Output:
    data   2D float32, shape (n_chroms, 7)
    dims   [chrom, statistic]
    statistic = [n_intervals, total_bp, mean_length, median_length,
                 min_length, max_length, span_bp]
    total_bp  = sum of (end - start) over all intervals
    span_bp   = max(end) - min(start) on this chrom
    median_length uses the middle value for odd counts, and the
    arithmetic mean of the two central values for even counts.

Params:
    region_dim  : record axis name (default "region")
    field_dim   : field axis name (default "field")
    chrom_field : chrom column label (default "chrom")
    start_field : start column label (default "chromStart")
    end_field   : end column label   (default "chromEnd")
    output      : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.core.numeric import compact_numeric
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = (
    "n_intervals", "total_bp", "mean_length", "median_length",
    "min_length", "max_length", "span_bp",
)


class IntervalStatsStep(Step):
    """Per-chromosome interval count and length statistics."""

    name = "interval_stats"
    category = "analysis"
    icon = "Ruler"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "region_dim": {"type": "string", "default": "region"},
            "field_dim": {"type": "string", "default": "field"},
            "chrom_field": {"type": "string", "default": "chrom"},
            "start_field": {"type": "string", "default": "chromStart"},
            "end_field": {"type": "string", "default": "chromEnd"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("region_dim", "region"),
              param("field_dim", "field")],
        info={
            "missing_code": MISSING,
            "encoders": {"type": "object", "optional": True},
        },
    )]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        rec_dim = ctx.step_params.get("region_dim", "region")
        fld_dim = ctx.step_params.get("field_dim", "field")
        chrom_field = ctx.step_params.get("chrom_field", "chrom")
        start_field = ctx.step_params.get("start_field", "chromStart")
        end_field = ctx.step_params.get("end_field", "chromEnd")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != rec_dim or form.dims[1] != fld_dim:
            raise StepError(
                f"interval_stats: expected 2D [{rec_dim},{fld_dim}], "
                f"got {form.dims}"
            )

        fld_labels = form.labels.get(fld_dim, {})
        for required in (chrom_field, start_field, end_field):
            if required not in fld_labels:
                raise StepError(
                    f"interval_stats: field dim '{fld_dim}' has no "
                    f"'{required}' label. Available: {sorted(fld_labels)}"
                )

        encoders = form.info.get("encoders", {}).get(fld_dim, {})
        chrom_enc = encoders.get(chrom_field)
        if chrom_enc is None:
            raise StepError(
                f"interval_stats: '{chrom_field}' column is not encoded"
            )

        chrom_codes = form.data[:, fld_labels[chrom_field]]
        starts = form.data[:, fld_labels[start_field]].astype(np.float64)
        ends = form.data[:, fld_labels[end_field]].astype(np.float64)

        if np.any(~np.isfinite(starts)) or np.any(~np.isfinite(ends)):
            raise StepError("interval_stats: start/end columns contain NaN")
        if np.any(ends <= starts):
            raise StepError(
                "interval_stats: end must be > start for every record"
            )

        by_chrom: dict[str, list[tuple[float, float]]] = {}
        for i in range(form.data.shape[0]):
            name = chrom_enc.inverse[int(round(float(chrom_codes[i])))]
            by_chrom.setdefault(name, []).append((starts[i], ends[i]))

        chrom_names = sorted(by_chrom)
        out_data = np.zeros((len(chrom_names), len(_STAT_LABELS)),
                            dtype=np.float64)

        for ci, chrom in enumerate(chrom_names):
            records = by_chrom[chrom]
            lens = np.array([e - s for s, e in records], dtype=np.float64)
            start_min = min(s for s, _ in records)
            end_max = max(e for _, e in records)
            out_data[ci, 0] = float(len(records))
            out_data[ci, 1] = float(lens.sum())
            out_data[ci, 2] = float(lens.mean())
            out_data[ci, 3] = float(np.median(lens))
            out_data[ci, 4] = float(lens.min())
            out_data[ci, 5] = float(lens.max())
            out_data[ci, 6] = float(end_max - start_min)

        out_data = compact_numeric(out_data)
        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "interval_stats"

        out_form = Form(
            data=out_data,
            dims=["chrom", "statistic"],
            labels={
                "chrom": {c: i for i, c in enumerate(chrom_names)},
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "region_dim": rec_dim,
            "field_dim": fld_dim,
            "n_chromosomes": len(chrom_names),
            "n_intervals": int(form.data.shape[0]),
            "chromosomes": chrom_names,
            "total_bp": float(out_data[:, 1].sum()),
            "median_interval_length": float(out_data[:, 3].mean()),
        }

        print(
            f"[interval_stats] {len(chrom_names)} chroms, "
            f"{int(form.data.shape[0])} intervals, "
            f"total_bp={int(out_data[:, 1].sum())}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
