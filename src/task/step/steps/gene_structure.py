"""Per-gene structure summary for any GFF3/GTF Form.

Input: Form from Gff3Reader or GtfReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [record, field]
    labels field = GFF3 column names, including attributes
    info   missing_code=NaN, encoders={field: {label: encoder}}

Gene membership comes from the attributes column: exon and CDS
records whose ``gene_id=`` (or ``Parent=``) matches a gene record
belong to that gene. When no gene_id linkage is present at all,
a positional fallback counts exon records contained in the gene
span.

Output:
    data   2D float32, shape (n_genes, 5)
    dims   [gene, statistic]
    statistic = [n_exons, n_introns, gene_length, cds_total, strand]
    strand = +1 or -1

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


_STAT_LABELS = ("n_exons", "n_introns", "gene_length", "cds_total", "strand")


class GeneStructureStep(Step):
    """Per-gene exon/intron/CDS summary for GFF3/GTF."""

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
        starts = form.data[:, fld_labels["start"]]
        ends = form.data[:, fld_labels["end"]]
        strand_codes = form.data[:, fld_labels["strand"]]

        # Parse attributes if present, to get gene_id linkage.
        attr_col = fld_labels.get("attributes")
        gene_id_by_record: list[str] | None = None
        if attr_col is not None:
            attr_enc = encoders.get("attributes")
            if attr_enc is not None:
                attr_codes = form.data[:, attr_col]
                raw_attrs = [
                    attr_enc.inverse.get(int(round(float(c))), "")
                    for c in attr_codes
                ]
                gene_id_by_record = []
                for a in raw_attrs:
                    gid = None
                    for part in str(a).split(";"):
                        if part.startswith("gene_id="):
                            gid = part.split("=", 1)[1]
                            break
                        if part.startswith("Parent="):
                            gid = part.split("=", 1)[1].split(",")[0]
                            break
                    gene_id_by_record.append(gid if gid else "")

        # Collect gene records.
        gene_records: list[dict] = []
        for i in range(form.data.shape[0]):
            tname = type_enc.inverse.get(int(round(float(type_codes[i]))), "")
            if tname != "gene":
                continue
            gene_records.append({
                "idx": i,
                "seqid": seqid_enc.inverse.get(
                    int(round(float(seqid_codes[i]))), ""
                ),
                "start": float(starts[i]),
                "end": float(ends[i]),
                "strand": strand_enc.inverse.get(
                    int(round(float(strand_codes[i]))), "+"
                ),
                "gene_id": (gene_id_by_record[i]
                            if gene_id_by_record is not None else ""),
            })

        if not gene_records:
            raise StepError(
                "gene_structure: no 'gene' records found in input"
            )

        # Bucket every record by its declared gene_id (if any).
        children_by_gene: dict[str, list[int]] = {}
        if gene_id_by_record is not None:
            for i in range(form.data.shape[0]):
                gid = gene_id_by_record[i]
                if gid:
                    children_by_gene.setdefault(gid, []).append(i)

        rows: list[list[float]] = []
        gene_names: list[str] = []

        for g in gene_records:
            gid = g["gene_id"]
            child_idxs = children_by_gene.get(gid, [])
            n_exons = 0
            cds_total = 0.0
            if child_idxs:
                for ci in child_idxs:
                    tname = type_enc.inverse.get(
                        int(round(float(type_codes[ci]))), ""
                    )
                    length = float(ends[ci] - starts[ci] + 1)
                    if tname == "exon":
                        n_exons += 1
                    elif tname == "CDS":
                        cds_total += length
            else:
                # Fallback: count exon records inside the gene span.
                gs, ge = g["start"], g["end"]
                gseq = g["seqid"]
                for i in range(form.data.shape[0]):
                    tname = type_enc.inverse.get(
                        int(round(float(type_codes[i]))), ""
                    )
                    if tname != "exon":
                        continue
                    if seqid_enc.inverse.get(
                        int(round(float(seqid_codes[i]))), ""
                    ) != gseq:
                        continue
                    if starts[i] >= gs and ends[i] <= ge:
                        n_exons += 1

            n_introns = max(0, n_exons - 1)
            strand_val = 1.0 if g["strand"] == "+" else -1.0
            gene_len = g["end"] - g["start"] + 1.0
            rows.append([
                float(n_exons), float(n_introns), gene_len,
                cds_total, strand_val,
            ])
            gene_names.append(gid if gid else f"gene_{len(gene_names)}")

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
            "n_genes": len(gene_records),
            "n_multi_exon_genes": multi_exon,
            "mean_exons": float(out_data[:, 0].mean()),
            "mean_gene_length": float(out_data[:, 2].mean()),
        }

        print(
            f"[gene_structure] {len(gene_records)} genes, "
            f"{multi_exon} multi-exon, "
            f"mean_exons={out_data[:, 0].mean():.2f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
