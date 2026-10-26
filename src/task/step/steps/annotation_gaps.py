"""Inter-gene gap statistics for any GFF3/GTF Form.

Groups gene records by seqid, sorts them by start position, and
reports the gap between every pair of consecutive genes.

gap_length = next.start - current.end - 1

Genes overlapping or touching each other (gap_length < 0 or 0)
are skipped. Gaps are reported per chromosome in start order.

Output:
    data   2D float32, shape (n_gaps, 5)
    dims   [gap, statistic]
    statistic = [gap_length, left_start, left_end, right_start, right_end]
    info["seqid"]      axis-parallel, name of the source chromosome
    info["left_gene"]  axis-parallel, "seqid:start-end" of the left gene
    info["right_gene"] axis-parallel, "seqid:start-end" of the right gene

Params:
    record_dim : name of the record axis (default "record")
    field_dim  : name of the field axis (default "field")
    min_gap    : report only gaps >= this many bp (default 0)
    output     : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("gap_length", "left_start", "left_end",
                "right_start", "right_end")


class AnnotationGapsStep(Step):
    """Inter-gene gap lengths for GFF3/GTF annotation QC."""
    title = 'annotation_gaps'
    description = 'Inter-gene gap lengths for GFF3/GTF annotation QC.'

    name = "annotation_gaps"
    category = "analysis"
    icon = "Ruler"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "record_dim": {"type": "string", "default": "record"},
            "field_dim": {"type": "string", "default": "field"},
            "min_gap": {"type": "integer", "minimum": 0, "default": 0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("record_dim", "record"),
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
        rec_dim = ctx.step_params.get("record_dim", "record")
        fld_dim = ctx.step_params.get("field_dim", "field")
        min_gap = int(ctx.step_params.get("min_gap", 0))
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != rec_dim or form.dims[1] != fld_dim:
            raise StepError(
                f"annotation_gaps: expected 2D [{rec_dim},{fld_dim}], "
                f"got {form.dims}"
            )

        fld_labels = form.labels.get(fld_dim, {})
        for required in ("seqid", "type", "start", "end"):
            if required not in fld_labels:
                raise StepError(
                    f"annotation_gaps: field dim '{fld_dim}' has no "
                    f"'{required}' label. Available: {sorted(fld_labels)}"
                )

        encoders = form.info.get("encoders", {}).get(fld_dim, {})
        type_enc = encoders.get("type")
        seqid_enc = encoders.get("seqid")
        for name, enc in (("type", type_enc), ("seqid", seqid_enc)):
            if enc is None:
                raise StepError(
                    f"annotation_gaps: '{name}' column is not encoded"
                )

        type_codes = form.data[:, fld_labels["type"]]
        seqid_codes = form.data[:, fld_labels["seqid"]]
        starts = form.data[:, fld_labels["start"]]
        ends = form.data[:, fld_labels["end"]]

        genes_by_seq: dict[str, list[tuple[float, float]]] = {}
        for i in range(form.data.shape[0]):
            if type_enc.inverse.get(int(round(float(type_codes[i])))) != "gene":
                continue
            sid = seqid_enc.inverse.get(
                int(round(float(seqid_codes[i]))), ""
            )
            genes_by_seq.setdefault(sid, []).append(
                (float(starts[i]), float(ends[i]))
            )

        if not genes_by_seq:
            raise StepError(
                "annotation_gaps: no 'gene' records found in input"
            )

        rows: list[list[float]] = []
        seqid_col: list[str] = []
        left_col: list[str] = []
        right_col: list[str] = []

        for sid in sorted(genes_by_seq):
            records = sorted(genes_by_seq[sid], key=lambda r: (r[0], r[1]))
            for j in range(len(records) - 1):
                ls, le = records[j]
                rs, re = records[j + 1]
                gap = rs - le - 1.0
                if gap < min_gap:
                    continue
                if gap < 0:
                    # Overlapping genes: no gap to report.
                    continue
                rows.append([gap, ls, le, rs, re])
                seqid_col.append(sid)
                left_col.append(f"{sid}:{int(ls)}-{int(le)}")
                right_col.append(f"{sid}:{int(rs)}-{int(re)}")

        if rows:
            out_data = np.asarray(rows, dtype=np.float32)
        else:
            out_data = np.zeros((0, len(_STAT_LABELS)), dtype=np.float32)

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "annotation_gaps"
        info["seqid"] = seqid_col
        info["left_gene"] = left_col
        info["right_gene"] = right_col

        axis_info = dict(axis_info)
        axis_info["gap"] = ["seqid", "left_gene", "right_gene"]

        out_form = Form(
            data=out_data,
            dims=["gap", "statistic"],
            labels={
                "gap": {str(i): i for i in range(len(rows))},
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        largest = float(out_data[:, 0].max()) if rows else 0.0
        self._export_data = {
            "record_dim": rec_dim,
            "field_dim": fld_dim,
            "min_gap": min_gap,
            "n_gaps": len(rows),
            "n_sequences": len(genes_by_seq),
            "largest_gap": largest,
        }

        print(
            f"[annotation_gaps] {len(rows)} gaps across "
            f"{len(genes_by_seq)} sequences, largest={largest:.0f} bp"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
