"""Associate every BED interval with its nearest annotated gene.

Inputs:
    A  BED   [region, field]  with chrom / chromStart / chromEnd
    B  GFF3  [record, field]  with seqid / type / start / end / strand

For every A interval, find the gene record on the same chromosome
whose span is closest. Overlapping intervals get distance 0.

Distance:
    overlap          -> 0
    A ends before B  -> B.start - A.end
    A starts after B -> A.start - B.end

Chromosome names are normalised before matching: if one side uses
"chr1" and the other "1", the "chr" prefix is added to the shorter
form. A column may or may not be encoded: if the reader encoded it,
the encoder's inverse is used; otherwise the numeric value is
stringified without a trailing ".0".

Output:
    data   2D float32, shape (n_peaks, 5)
    dims   [peak, statistic]
    statistic = [distance, gene_start, gene_end, gene_length, strand]
    info["peak_id"]  axis-parallel, index of the A interval
    info["gene_id"]  axis-parallel, gene id from attributes or "g<i>"
    info["chrom"]    axis-parallel, normalised chromosome name

Params:
    a_region_dim   : A record axis  (default "region")
    a_field_dim    : A field axis   (default "field")
    a_chrom_field  : A chrom column (default "chrom")
    a_start_field  : A start column (default "chromStart")
    a_end_field    : A end column   (default "chromEnd")
    b_record_dim   : B record axis  (default "record")
    b_field_dim    : B field axis   (default "field")
    b_chrom_field  : B seqid column (default "seqid")
    b_start_field  : B start column (default "start")
    b_end_field    : B end column   (default "end")
    b_strand_field : B strand column (default "strand")
    feature_type   : only use B records whose type equals this
                     (default "gene"; set to "" to disable)
    max_distance   : report only peaks with distance <= this many bp
                     (default null = no limit)
    output         : context key for the result (default: step name)
"""
from __future__ import annotations

import bisect

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.reader.readers._labels import unique_labels
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("distance", "gene_start", "gene_end",
                "gene_length", "strand")


def _normalise_chrom(name: str) -> str:
    name = str(name)
    return name if name.startswith("chr") else "chr" + name


def _num_to_chrom(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _decode_column(values, encoder):
    if encoder is not None:
        return [encoder.inverse[int(round(float(v)))] for v in values]
    return [_num_to_chrom(float(v)) for v in values]


def _read_intervals(form, region_dim, field_dim, chrom_field,
                    start_field, end_field, label):
    if form.data.ndim != 2 or form.dims[0] != region_dim or form.dims[1] != field_dim:
        raise StepError(
            f"peak_nearest_gene: {label} expected 2D "
            f"[{region_dim},{field_dim}], got {form.dims}"
        )
    fld_labels = form.labels.get(field_dim, {})
    for required in (chrom_field, start_field, end_field):
        if required not in fld_labels:
            raise StepError(
                f"peak_nearest_gene: {label} field dim '{field_dim}' "
                f"has no '{required}' label. Available: "
                f"{sorted(fld_labels)}"
            )
    encoders = form.info.get("encoders", {}).get(field_dim, {})
    chrom_enc = encoders.get(chrom_field)
    chrom_codes = form.data[:, fld_labels[chrom_field]]
    starts = form.data[:, fld_labels[start_field]].astype(np.float64)
    ends = form.data[:, fld_labels[end_field]].astype(np.float64)
    if np.any(~np.isfinite(starts)) or np.any(~np.isfinite(ends)):
        raise StepError(
            f"peak_nearest_gene: {label} start/end contain NaN"
        )
    if np.any(ends <= starts):
        raise StepError(
            f"peak_nearest_gene: {label} end must be > start"
        )
    names = _decode_column(chrom_codes, chrom_enc)
    return starts, ends, names


class PeakNearestGeneStep(Step):
    """Assign every BED interval to its nearest annotated gene."""
    title = 'peak_nearest_gene'
    description = 'Assign every BED interval to its nearest annotated gene.'

    name = "peak_nearest_gene"
    category = "analysis"
    icon = "Dna"
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
            "b_record_dim": {"type": "string", "default": "record"},
            "b_field_dim": {"type": "string", "default": "field"},
            "b_chrom_field": {"type": "string", "default": "seqid"},
            "b_start_field": {"type": "string", "default": "start"},
            "b_end_field": {"type": "string", "default": "end"},
            "b_strand_field": {"type": "string", "default": "strand"},
            "feature_type": {"type": "string", "default": "gene"},
            "max_distance": {"type": ["integer", "null"], "minimum": 0,
                             "default": None},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }
    input_contracts = [
        port(
            ndim=2,
            dims=[param("a_region_dim", "region"), param("a_field_dim", "field")],
            info={"missing_code": MISSING,
                  "encoders": {"type": "object", "optional": True}},
        ),
        port(
            ndim=2,
            dims=[param("b_record_dim", "record"), param("b_field_dim", "field")],
            info={"missing_code": MISSING,
                  "encoders": {"type": "object", "optional": True}},
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
        b_record_dim = ctx.step_params.get("b_record_dim", "record")
        b_field_dim = ctx.step_params.get("b_field_dim", "field")
        b_chrom = ctx.step_params.get("b_chrom_field", "seqid")
        b_start = ctx.step_params.get("b_start_field", "start")
        b_end = ctx.step_params.get("b_end_field", "end")
        b_strand = ctx.step_params.get("b_strand_field", "strand")
        feature_type = ctx.step_params.get("feature_type", "gene")
        max_distance = ctx.step_params.get("max_distance")
        out_name = ctx.step_params.get("output", self.name)

        a_starts, a_ends, a_chroms = _read_intervals(
            a_form, a_region_dim, a_field_dim, a_chrom, a_start, a_end, "A"
        )
        b_starts, b_ends, b_chroms = _read_intervals(
            b_form, b_record_dim, b_field_dim, b_chrom, b_start, b_end, "B"
        )

        b_fld_labels = b_form.labels.get(b_field_dim, {})
        b_encoders = b_form.info.get("encoders", {}).get(b_field_dim, {})

        # Optional feature type filter on B.
        b_type_codes = None
        b_type_enc = None
        if feature_type:
            if "type" not in b_fld_labels:
                raise StepError(
                    f"peak_nearest_gene: B field dim has no 'type' label; "
                    f"cannot apply feature_type='{feature_type}'"
                )
            b_type_enc = b_encoders.get("type")
            if b_type_enc is None:
                raise StepError(
                    "peak_nearest_gene: B 'type' column is not encoded"
                )
            b_type_codes = b_form.data[:, b_fld_labels["type"]]

        # Strand: encoded or not.
        if b_strand not in b_fld_labels:
            raise StepError(
                f"peak_nearest_gene: B field dim has no '{b_strand}' label"
            )
        b_strand_enc = b_encoders.get(b_strand)
        b_strand_codes = b_form.data[:, b_fld_labels[b_strand]]

        def decode_strand(value):
            if b_strand_enc is not None:
                return b_strand_enc.inverse[int(round(float(value)))]
            return "+" if float(value) >= 0 else "-"

        # Gene id from attributes if present, else positional.
        b_attr_col = b_fld_labels.get("attributes")
        b_attr_enc = b_encoders.get("attributes") if b_attr_col is not None else None
        gene_names_raw: list[str] = []
        for i in range(b_form.data.shape[0]):
            if b_attr_col is not None and b_attr_enc is not None:
                code = int(round(float(b_form.data[i, b_attr_col])))
                raw = b_attr_enc.inverse.get(code, "")
                gid = None
                for part in str(raw).split(";"):
                    for prefix in ("gene_id=", "ID=", "Parent="):
                        if part.startswith(prefix):
                            gid = part.split("=", 1)[1].split(",")[0]
                            break
                    if gid:
                        break
                gene_names_raw.append(gid or f"g{i}")
            else:
                gene_names_raw.append(f"g{i}")

        # Group B by normalised chromosome.
        by_chrom: dict[str, list[tuple[float, float, str, float]]] = {}
        for i in range(b_form.data.shape[0]):
            if b_type_codes is not None:
                tname = b_type_enc.inverse.get(
                    int(round(float(b_type_codes[i]))), ""
                )
                if tname != feature_type:
                    continue
            strand_name = decode_strand(b_strand_codes[i])
            strand_val = 1.0 if strand_name == "+" else -1.0
            cname = _normalise_chrom(b_chroms[i])
            by_chrom.setdefault(cname, []).append(
                (b_starts[i], b_ends[i], gene_names_raw[i], strand_val)
            )

        if not by_chrom:
            raise StepError(
                f"peak_nearest_gene: no B records matched "
                f"feature_type='{feature_type}'"
            )

        chrom_index: dict[str, tuple[list[float], list[tuple]]] = {}
        for chrom, records in by_chrom.items():
            records.sort(key=lambda r: r[0])
            chrom_index[chrom] = ([r[0] for r in records], records)

        rows: list[list[float]] = []
        peak_col: list[str] = []
        gene_col: list[str] = []
        chrom_col: list[str] = []
        n_skipped_chrom = 0
        n_skipped_distance = 0

        for i in range(a_form.data.shape[0]):
            chrom = _normalise_chrom(a_chroms[i])
            if chrom not in chrom_index:
                n_skipped_chrom += 1
                continue
            gene_starts, genes = chrom_index[chrom]
            ps, pe = a_starts[i], a_ends[i]

            pos = bisect.bisect_left(gene_starts, ps)
            candidates = set()
            for k in (pos - 2, pos - 1, pos, pos + 1):
                if 0 <= k < len(genes):
                    candidates.add(k)

            best = None
            best_dist = None
            for k in sorted(candidates):
                gs, ge, gid, strand_val = genes[k]
                if ge <= ps:
                    d = ps - ge
                elif gs >= pe:
                    d = gs - pe
                else:
                    d = 0
                if best_dist is None or d < best_dist:
                    best_dist = d
                    best = (gs, ge, gid, strand_val)

            if best is None:
                n_skipped_chrom += 1
                continue
            if max_distance is not None and best_dist > max_distance:
                n_skipped_distance += 1
                continue

            gs, ge, gid, strand_val = best
            rows.append([
                float(best_dist), float(gs), float(ge),
                float(ge - gs), float(strand_val),
            ])
            peak_col.append(str(i))
            gene_col.append(gid)
            chrom_col.append(chrom)

        if rows:
            out_data = np.asarray(rows, dtype=np.float32)
        else:
            out_data = np.zeros((0, len(_STAT_LABELS)), dtype=np.float32)

        peak_ids = unique_labels(peak_col, "peak", "peak_nearest_gene")

        info, axis_info = project_metadata(a_form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "peak_nearest_gene"
        info["peak_id"] = peak_col
        info["gene_id"] = gene_col
        info["chrom"] = chrom_col

        axis_info = dict(axis_info)
        axis_info["peak"] = ["peak_id", "gene_id", "chrom"]

        out_form = Form(
            data=out_data,
            dims=["peak", "statistic"],
            labels={
                "peak": peak_ids,
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        n_a = int(a_form.data.shape[0])
        n_kept = len(rows)
        self._export_data = {
            "n_peaks": n_a,
            "n_kept": n_kept,
            "n_skipped_no_chrom": n_skipped_chrom,
            "n_skipped_distance": n_skipped_distance,
            "feature_type": feature_type,
            "max_distance": max_distance,
            "n_overlapping_genes": int((out_data[:, 0] == 0).sum()) if rows else 0,
            "mean_distance": float(out_data[:, 0].mean()) if rows else 0.0,
        }

        print(
            f"[peak_nearest_gene] {n_a} peaks -> {n_kept} annotated, "
            f"skipped (chrom)={n_skipped_chrom}, "
            f"skipped (distance)={n_skipped_distance}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
