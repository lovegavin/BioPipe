"""Pairwise interval overlap between two BED forms (bedtools intersect style).

Inputs: two Forms from BedReader (or any form with chrom/start/end
columns). Each record is a half-open interval [start, end) on a chrom.

Output: every (A, B) pair whose intervals overlap by at least
``min_overlap`` bases.
    data   2D float32, shape (n_pairs, 7)
    dims   [pair, statistic]
    statistic = [overlap_start, overlap_end, overlap_length,
                 a_length, b_length,
                 overlap_fraction_a, overlap_fraction_b]
    info["chrom"]  axis-parallel, chromosome of each pair
    info["a_id"]   axis-parallel, index of the A interval
    info["b_id"]   axis-parallel, index of the B interval

Both inputs are grouped by chromosome and scanned with a sweep-line:
each A-start is matched against every currently open B interval, and
vice versa. Each pair is recorded exactly once.

Params:
    a_region_dim  : A record axis (default "region")
    a_field_dim   : A field axis (default "field")
    a_chrom_field : A chrom column (default "chrom")
    a_start_field : A start column (default "chromStart")
    a_end_field   : A end column (default "chromEnd")
    b_region_dim  : B record axis (default "region")
    b_field_dim   : B field axis (default "field")
    b_chrom_field : B chrom column (default "chrom")
    b_start_field : B start column (default "chromStart")
    b_end_field   : B end column (default "chromEnd")
    min_overlap   : minimum overlap in bp (default 1)
    max_output    : abort with an error above this many pairs (default 1000000)
    output        : context key for the result (default: step name)
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
    "overlap_start", "overlap_end", "overlap_length",
    "a_length", "b_length",
    "overlap_fraction_a", "overlap_fraction_b",
)


def _extract(form, region_dim, field_dim, chrom_field, start_field, end_field,
             label):
    if form.data.ndim != 2 or form.dims[0] != region_dim or form.dims[1] != field_dim:
        raise StepError(
            f"interval_overlap: {label} expected 2D "
            f"[{region_dim},{field_dim}], got {form.dims}"
        )
    fld_labels = form.labels.get(field_dim, {})
    for required in (chrom_field, start_field, end_field):
        if required not in fld_labels:
            raise StepError(
                f"interval_overlap: {label} field dim '{field_dim}' has no "
                f"'{required}' label. Available: {sorted(fld_labels)}"
            )
    encoders = form.info.get("encoders", {}).get(field_dim, {})
    chrom_enc = encoders.get(chrom_field)
    chrom_codes = form.data[:, fld_labels[chrom_field]]
    starts = form.data[:, fld_labels[start_field]].astype(np.float64)
    ends = form.data[:, fld_labels[end_field]].astype(np.float64)
    if np.any(~np.isfinite(starts)) or np.any(~np.isfinite(ends)):
        raise StepError(f"interval_overlap: {label} start/end contain NaN")
    if np.any(ends <= starts):
        raise StepError(
            f"interval_overlap: {label} end must be > start for every record"
        )

    if chrom_enc is not None:
        names = [chrom_enc.inverse[int(round(float(c)))] for c in chrom_codes]
    else:
        names = [_num_to_chrom(float(c)) for c in chrom_codes]

    by_chrom: dict[str, list[tuple[float, float, int]]] = {}
    for i in range(form.data.shape[0]):
        by_chrom.setdefault(names[i], []).append((starts[i], ends[i], i))
    return by_chrom


def _num_to_chrom(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


class IntervalOverlapStep(Step):
    """Pairwise overlap of intervals between two BED forms."""

    name = "interval_overlap"
    category = "analysis"
    icon = "Intersect"
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "a_region_dim": {"type": "string", "default": "region"},
            "a_field_dim": {"type": "string", "default": "field"},
            "a_chrom_field": {"type": "string", "default": "chrom"},
            "a_start_field": {"type": "string", "default": "chromStart"},
            "a_end_field": {"type": "string", "default": "chromEnd"},
            "b_region_dim": {"type": "string", "default": "region"},
            "b_field_dim": {"type": "string", "default": "field"},
            "b_chrom_field": {"type": "string", "default": "chrom"},
            "b_start_field": {"type": "string", "default": "chromStart"},
            "b_end_field": {"type": "string", "default": "chromEnd"},
            "min_overlap": {"type": "integer", "minimum": 1, "default": 1},
            "max_output": {"type": "integer", "minimum": 1, "default": 1000000},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }
    input_contracts = [
        port(
            ndim=2,
            dims=[param("a_region_dim", "region"), param("a_field_dim", "field")],
            info={
                "missing_code": MISSING,
                "encoders": {"type": "object", "optional": True},
            },
        ),
        port(
            ndim=2,
            dims=[param("b_region_dim", "region"), param("b_field_dim", "field")],
            info={
                "missing_code": MISSING,
                "encoders": {"type": "object", "optional": True},
            },
        ),
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

    def run(self, ctx: Context, inputs) -> None:
        a_form, b_form = inputs
        a_region_dim = ctx.step_params.get("a_region_dim", "region")
        a_field_dim = ctx.step_params.get("a_field_dim", "field")
        a_chrom = ctx.step_params.get("a_chrom_field", "chrom")
        a_start = ctx.step_params.get("a_start_field", "chromStart")
        a_end = ctx.step_params.get("a_end_field", "chromEnd")
        b_region_dim = ctx.step_params.get("b_region_dim", "region")
        b_field_dim = ctx.step_params.get("b_field_dim", "field")
        b_chrom = ctx.step_params.get("b_chrom_field", "chrom")
        b_start = ctx.step_params.get("b_start_field", "chromStart")
        b_end = ctx.step_params.get("b_end_field", "chromEnd")
        min_overlap = int(ctx.step_params.get("min_overlap", 1))
        max_output = int(ctx.step_params.get("max_output", 1_000_000))
        out_name = ctx.step_params.get("output", self.name)

        if min_overlap < 1:
            raise StepError(
                f"interval_overlap: min_overlap must be >= 1, got {min_overlap}"
            )

        a_by_chrom = _extract(
            a_form, a_region_dim, a_field_dim, a_chrom, a_start, a_end, "A"
        )
        b_by_chrom = _extract(
            b_form, b_region_dim, b_field_dim, b_chrom, b_start, b_end, "B"
        )

        common_chroms = sorted(set(a_by_chrom) & set(b_by_chrom))

        rows: list[list[float]] = []
        chrom_col: list[str] = []
        a_id_col: list[str] = []
        b_id_col: list[str] = []
        n_pairs = 0

        for chrom in common_chroms:
            a_records = sorted(a_by_chrom[chrom], key=lambda r: r[0])
            b_records = sorted(b_by_chrom[chrom], key=lambda r: r[0])
            if not a_records or not b_records:
                continue

            # Build sweep events: (pos, kind, side, idx_in_local_list)
            # kind: 0 = start, 1 = end. At the same pos, starts first
            # so that half-open intervals do not falsely overlap.
            events: list[tuple[float, int, int, int]] = []
            for j, (s, e, _) in enumerate(a_records):
                events.append((s, 0, 0, j))
                events.append((e, 1, 0, j))
            for j, (s, e, _) in enumerate(b_records):
                events.append((s, 0, 1, j))
                events.append((e, 1, 1, j))
            events.sort(key=lambda ev: (ev[0], ev[1], ev[2]))

            a_active: dict[int, None] = {}
            b_active: dict[int, None] = {}

            for pos, kind, side, j in events:
                if kind == 0:  # start
                    if side == 0:
                        # New A: pair with every active B.
                        if b_active:
                            a_s = a_records[j][0]
                            a_e = a_records[j][1]
                            for k in list(b_active):
                                b_s, b_e, _ = b_records[k]
                                ov_s = a_s if a_s > b_s else b_s
                                ov_e = a_e if a_e < b_e else b_e
                                ov_len = ov_e - ov_s
                                if ov_len >= min_overlap:
                                    a_len = a_e - a_s
                                    b_len = b_e - b_s
                                    rows.append([
                                        float(ov_s), float(ov_e),
                                        float(ov_len),
                                        float(a_len), float(b_len),
                                        float(ov_len / a_len),
                                        float(ov_len / b_len),
                                    ])
                                    chrom_col.append(chrom)
                                    a_id_col.append(str(a_records[j][2]))
                                    b_id_col.append(str(b_records[k][2]))
                                    n_pairs += 1
                                    if n_pairs > max_output:
                                        raise StepError(
                                            f"interval_overlap: exceeded "
                                            f"max_output={max_output} pairs"
                                        )
                        a_active[j] = None
                    else:
                        # New B: pair with every active A.
                        if a_active:
                            b_s = b_records[j][0]
                            b_e = b_records[j][1]
                            for k in list(a_active):
                                a_s, a_e, _ = a_records[k]
                                ov_s = a_s if a_s > b_s else b_s
                                ov_e = a_e if a_e < b_e else b_e
                                ov_len = ov_e - ov_s
                                if ov_len >= min_overlap:
                                    a_len = a_e - a_s
                                    b_len = b_e - b_s
                                    rows.append([
                                        float(ov_s), float(ov_e),
                                        float(ov_len),
                                        float(a_len), float(b_len),
                                        float(ov_len / a_len),
                                        float(ov_len / b_len),
                                    ])
                                    chrom_col.append(chrom)
                                    a_id_col.append(str(a_records[k][2]))
                                    b_id_col.append(str(b_records[j][2]))
                                    n_pairs += 1
                                    if n_pairs > max_output:
                                        raise StepError(
                                            f"interval_overlap: exceeded "
                                            f"max_output={max_output} pairs"
                                        )
                        b_active[j] = None
                else:  # end
                    if side == 0:
                        a_active.pop(j, None)
                    else:
                        b_active.pop(j, None)

        if rows:
            out_data = compact_numeric(np.asarray(rows, dtype=np.float64))
        else:
            out_data = np.zeros((0, len(_STAT_LABELS)), dtype=np.float32)

        pair_ids = [f"pair_{i}" for i in range(len(rows))]

        info, axis_info = project_metadata(a_form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "interval_overlaps"
        info["chrom"] = chrom_col
        info["a_id"] = a_id_col
        info["b_id"] = b_id_col

        axis_info = dict(axis_info)
        axis_info["pair"] = ["chrom", "a_id", "b_id"]

        out_form = Form(
            data=out_data,
            dims=["pair", "statistic"],
            labels={
                "pair": {p: i for i, p in enumerate(pair_ids)},
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "min_overlap": min_overlap,
            "max_output": max_output,
            "n_pairs": n_pairs,
            "n_chromosomes_shared": len(common_chroms),
            "n_a_intervals": int(a_form.data.shape[0]),
            "n_b_intervals": int(b_form.data.shape[0]),
            "total_overlap_bp": float(out_data[:, 2].sum()) if rows else 0.0,
            "mean_overlap_length": float(out_data[:, 2].mean()) if rows else 0.0,
        }

        print(
            f"[interval_overlap] {n_pairs} pairs across "
            f"{len(common_chroms)} shared chromosomes, "
            f"min_overlap={min_overlap}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
