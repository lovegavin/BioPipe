"""Per-gene structure summary for any GFF3 / GTF Form.

Input: Form from Gff3Reader or GtfReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [record, field]
    labels field = column names including type / start / end / strand
    info   missing_code=NaN, encoders={field: {label: encoder}}

Every record whose type is "gene" becomes one output row. Exon and
CDS counts, together with the CDS length, are computed by span
containment: a record is attributed to a gene when its seqid matches
and its interval lies inside the gene's [start, end] range.

GFF3 and GTF both express gene -> mRNA -> exon hierarchies. The
hierarchy varies by file and is not always complete, so this operator
uses span containment instead of parent-id lookups. Nested genes
(gene fully contained inside another gene) would be mis-attributed,
which is rare enough to be acceptable for annotation QC.

Output:
    data   2D float32, shape (n_genes, 5)
    dims   [gene, statistic]
    statistic = (n_exons, n_introns, gene_length, cds_total, strand)

Params:
    record_dim : record axis (default "record")
    field_dim  : field axis  (default "field")
    output     : context key (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("n_exons", "n_introns", "gene_length", "cds_total", "strand")


class GeneStructureStep(Step):
    """Per-gene exon/intron/CDS summary by span containment."""

    name = "gene_structure"
    category = "analysis"
    icon = "TreeStructure"
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
                f"gene_structure: expected 2D [{rec_dim},{fld_dim}], "
                f"got {form.dims}"
            )

        fld_labels = form.labels.get(fld_dim, {})
        for required in ("seqid", "type", "start", "end", "strand"):
            if required not in fld_labels:
                raise StepError(
                    f"gene_structure: field dim '{fld_dim}' has no "
                    f"'{required}' label. Available: {sorted(fld_labels)}"
                )

        encoders = form.info.get("encoders", {}).get(fld_dim, {})
        type_enc = encoders.get("type")
        seqid_enc = encoders.get("seqid")
        strand_enc = encoders.get("strand")
        for name, enc in (("type", type_enc), ("seqid", seqid_enc),
                          ("strand", strand_enc)):
            if enc is None:
                raise StepError(
                    f"gene_structure: '{name}' column is not encoded"
                )

        type_codes = form.data[:, fld_labels["type"]]
        seqid_codes = form.data[:, fld_labels["seqid"]]
        starts = form.data[:, fld_labels["start"]].astype(np.float64)
        ends = form.data[:, fld_labels["end"]].astype(np.float64)
        strand_codes = form.data[:, fld_labels["strand"]]

        if np.any(~np.isfinite(starts)) or np.any(~np.isfinite(ends)):
            raise StepError("gene_structure: start/end columns contain NaN")

        type_per_record = [
            type_enc.inverse.get(int(round(float(c))), "") for c in type_codes
        ]
        seqid_per_record = [
            seqid_enc.inverse.get(int(round(float(c))), "") for c in seqid_codes
        ]
        strand_per_record = [
            strand_enc.inverse.get(int(round(float(c))), "+")
            for c in strand_codes
        ]

        gene_indices = [i for i, t in enumerate(type_per_record) if t == "gene"]
        if not gene_indices:
            raise StepError(
                "gene_structure: no 'gene' records found in input"
            )

        exon_indices = [i for i, t in enumerate(type_per_record) if t == "exon"]
        cds_indices = [i for i, t in enumerate(type_per_record) if t == "CDS"]

        # Group exons and CDS by seqid so containment checks only look
        # at records on the same chromosome.
        exons_by_chrom: dict[str, list[tuple[float, float]]] = {}
        for i in exon_indices:
            exons_by_chrom.setdefault(seqid_per_record[i], []).append(
                (starts[i], ends[i])
            )
        cds_by_chrom: dict[str, list[tuple[float, float]]] = {}
        for i in cds_indices:
            cds_by_chrom.setdefault(seqid_per_record[i], []).append(
                (starts[i], ends[i])
            )

        # Attributes column, if present, provides stable gene names.
        attr_col = fld_labels.get("attributes")
        attr_enc = encoders.get("attributes") if attr_col is not None else None

        def gene_name(i):
            if attr_col is not None and attr_enc is not None:
                code = int(round(float(form.data[i, attr_col])))
                raw = attr_enc.inverse.get(code, "")
                for part in str(raw).split(";"):
                    for prefix in ("gene_id=", "ID="):
                        if part.startswith(prefix):
                            value = part.split("=", 1)[1].split(",")[0]
                            # Strip GFF3 type prefix like "gene:YAL069W".
                            if ":" in value:
                                value = value.split(":", 1)[1]
                            return value
            return f"gene_{i}"

        rows: list[list[float]] = []
        gene_names: list[str] = []

        for gi in gene_indices:
            gs = float(starts[gi])
            ge = float(ends[gi])
            gseq = seqid_per_record[gi]
            strand_name = strand_per_record[gi]
            strand_val = 1.0 if strand_name == "+" else -1.0

            n_exons = 0
            for (es, ee) in exons_by_chrom.get(gseq, []):
                if es >= gs and ee <= ge:
                    n_exons += 1
            cds_total = 0.0
            for (cs, ce) in cds_by_chrom.get(gseq, []):
                if cs >= gs and ce <= ge:
                    cds_total += float(ce - cs + 1.0)

            n_introns = max(0, n_exons - 1)
            gene_len = ge - gs + 1.0
            rows.append([
                float(n_exons), float(n_introns), gene_len,
                cds_total, strand_val,
            ])
            gene_names.append(gene_name(gi))

        out_data = np.asarray(rows, dtype=np.float32)

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "gene_structure"

        out_form = Form(
            data=out_data,
            dims=["gene", "statistic"],
            labels={
                "gene": {n: i for i, n in enumerate(gene_names)},
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        multi_exon = int((out_data[:, 0] > 1).sum())
        self._export_data = {
            "record_dim": rec_dim,
            "field_dim": fld_dim,
            "n_genes": len(gene_indices),
            "n_multi_exon_genes": multi_exon,
            "mean_exons": float(out_data[:, 0].mean()),
            "mean_gene_length": float(out_data[:, 2].mean()),
        }

        print(
            f"[gene_structure] {len(gene_indices)} genes, "
            f"{multi_exon} multi-exon, "
            f"mean_exons={out_data[:, 0].mean():.2f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
