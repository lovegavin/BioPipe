"""Inter-gene gap statistics for any GFF3/GTF Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.core.numeric import compact_numeric
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_columns import require_role


_STAT_LABELS = ("gap_length", "left_start", "left_end",
                "right_start", "right_end")


class AnnotationGapsStep(Step):
    """Inter-gene gap lengths for GFF3/GTF annotation QC."""

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
        encoders = form.info.get("encoders", {}).get(fld_dim, {})

        _, seqid_idx, seqid_enc = require_role(
            fld_labels, encoders, "seqid", "annotation_gaps",
        )
        _, type_idx, type_enc = require_role(
            fld_labels, encoders, "type", "annotation_gaps",
        )
        _, start_idx, _ = require_role(
            fld_labels, encoders, "start", "annotation_gaps",
            require_encoder=False,
        )
        _, end_idx, _ = require_role(
            fld_labels, encoders, "end", "annotation_gaps",
            require_encoder=False,
        )

        type_codes = form.data[:, type_idx]
        seqid_codes = form.data[:, seqid_idx]
        starts = form.data[:, start_idx]
        ends = form.data[:, end_idx]

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
                    continue
                rows.append([gap, ls, le, rs, re])
                seqid_col.append(sid)
                left_col.append(f"{sid}:{int(ls)}-{int(le)}")
                right_col.append(f"{sid}:{int(rs)}-{int(re)}")

        if rows:
            out_data = compact_numeric(np.asarray(rows, dtype=np.float64))
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
