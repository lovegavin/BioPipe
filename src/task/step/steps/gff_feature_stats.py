"""Per-feature-type statistics for any GFF3/GTF Form.

Input: Form from Gff3Reader or GtfReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [record, field]
    labels field = GFF3 column names (seqid, source, type, start,
                   end, score, strand, phase, attributes)
    info   missing_code=NaN, encoders={field: {label: encoder}}

Output:
    data   2D float32, shape (n_types, 6)
    dims   [feature_type, statistic]
    statistic = [count, total_length, mean_length, min_length,
                 max_length, mean_exons_per_gene]

mean_exons_per_gene is the ratio of "exon" records to "gene"
records in the whole file; it is only meaningful for the "gene"
row, and is 0 for every other feature type.

Params:
    record_dim : name of the record axis (default "record")
    field_dim  : name of the field axis (default "field")
    output     : context key for the result (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = (
    "count", "total_length", "mean_length",
    "min_length", "max_length", "mean_exons_per_gene",
)


class GffFeatureStatsStep(Step):
    """Per-feature-type length and count statistics for GFF3/GTF."""

    name = "gff_feature_stats"
    category = "analysis"
    icon = "Columns"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "record_dim": {"type": "string", "default": "record"},
            "field_dim": {"type": "string", "default": "field"},
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
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != rec_dim or form.dims[1] != fld_dim:
            raise StepError(
                f"gff_feature_stats: expected 2D [{rec_dim},{fld_dim}], "
                f"got {form.dims}"
            )

        fld_labels = form.labels.get(fld_dim, {})
        for required in ("type", "start", "end"):
            if required not in fld_labels:
                raise StepError(
                    f"gff_feature_stats: field dim '{fld_dim}' has no "
                    f"'{required}' label. Available: {sorted(fld_labels)}"
                )

        encoders = form.info.get("encoders", {}).get(fld_dim, {})
        type_enc = encoders.get("type")
        if type_enc is None:
            raise StepError(
                "gff_feature_stats: 'type' column is not encoded; "
                "Gff3Reader should have encoded it"
            )

        type_codes = form.data[:, fld_labels["type"]]
        starts = form.data[:, fld_labels["start"]]
        ends = form.data[:, fld_labels["end"]]

        lengths = ends - starts + 1.0

        type_names = sorted({
            type_enc.inverse[int(round(float(c)))]
            for c in np.unique(type_codes)
        })

        n_types = len(type_names)
        out_data = np.zeros((n_types, len(_STAT_LABELS)), dtype=np.float32)

        type_position = {
            type_enc.inverse[int(round(float(c)))]: i
            for i, c in enumerate(type_codes)
        }
        name_per_record = [
            type_enc.inverse[int(round(float(c)))] for c in type_codes
        ]

        for i, t in enumerate(type_names):
            mask = np.array([n == t for n in name_per_record])
            if not mask.any():
                continue
            lens = lengths[mask]
            out_data[i, 0] = float(mask.sum())
            out_data[i, 1] = float(lens.sum())
            out_data[i, 2] = float(lens.mean())
            out_data[i, 3] = float(lens.min())
            out_data[i, 4] = float(lens.max())

        n_gene = float(sum(1 for n in name_per_record if n == "gene"))
        n_exon = float(sum(1 for n in name_per_record if n == "exon"))
        if n_gene > 0 and "gene" in type_names:
            idx = type_names.index("gene")
            out_data[idx, 5] = n_exon / n_gene

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "gff_feature_stats"

        out_form = Form(
            data=out_data,
            dims=["feature_type", "statistic"],
            labels={
                "feature_type": {t: i for i, t in enumerate(type_names)},
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "record_dim": rec_dim,
            "field_dim": fld_dim,
            "n_records": int(form.data.shape[0]),
            "feature_types": type_names,
            "n_feature_types": n_types,
            "total_genes": int(n_gene),
            "total_exons": int(n_exon),
            "mean_exons_per_gene": (n_exon / n_gene) if n_gene else 0.0,
        }

        print(
            f"[gff_feature_stats] {n_types} feature types, "
            f"{int(n_gene)} genes, {int(n_exon)} exons, "
            f"mean_exons_per_gene={n_exon / n_gene if n_gene else 0:.2f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
