"""Per-gene structure summary for any GFF3 / GTF Form.

Input: Form from Gff3Reader or GtfReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [record, field]
    labels field includes seqid / type / start / end / strand, plus
           optionally attributes (GFF3: 'attributes', GTF: 'attribute')
    info   missing_code=NaN, encoders={field: {column: encoder}}

Every record whose feature type is exactly "gene" becomes one output
row. Exon and CDS records are attributed to their parent gene using
the annotation's own parent chain:

  * GTF: each exon / CDS record carries ``gene_id "X"`` directly.
  * GFF3: each exon / CDS record carries ``Parent=transcript:Y``; the
    transcript record Y carries ``Parent=gene:X``.

Records whose parent chain resolves to a gene that is not in the
"gene" feature set (for example an exon of an ``ncRNA_gene``) are
skipped. When a record carries no attribute information at all
(minimal fixtures), the operator falls back to span containment: the
record is attributed to the first gene whose span on the same
sequence contains it. Span containment mis-attributes nested genes,
so it is used only when the parent chain is unavailable.

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
from src.core.numeric import compact_numeric
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_columns import (
    parse_direct_gene_id,
    parse_gene_id,
    parse_parent,
    parse_record_id,
    require_role,
    try_role,
)


_STAT_LABELS = ("n_exons", "n_introns", "gene_length", "cds_total", "strand")


class GeneStructureStep(Step):
    """Per-gene exon/intron/CDS summary for GFF3/GTF annotations."""

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
        encoders = form.info.get("encoders", {}).get(fld_dim, {})

        _, seqid_idx, seqid_enc = require_role(
            fld_labels, encoders, "seqid", "gene_structure",
        )
        _, type_idx, type_enc = require_role(
            fld_labels, encoders, "type", "gene_structure",
        )
        _, start_idx, _ = require_role(
            fld_labels, encoders, "start", "gene_structure",
            require_encoder=False,
        )
        _, end_idx, _ = require_role(
            fld_labels, encoders, "end", "gene_structure",
            require_encoder=False,
        )
        _, strand_idx, strand_enc = require_role(
            fld_labels, encoders, "strand", "gene_structure",
        )
        attr_name, attr_idx, attr_enc = try_role(
            fld_labels, encoders, "attributes",
        )

        starts = form.data[:, start_idx].astype(np.float64)
        ends = form.data[:, end_idx].astype(np.float64)
        if np.any(~np.isfinite(starts)) or np.any(~np.isfinite(ends)):
            raise StepError("gene_structure: start/end columns contain NaN")

        n_records = form.data.shape[0]

        def decode(enc, idx, default=""):
            return [
                enc.inverse.get(int(round(float(form.data[i, idx]))), default)
                for i in range(n_records)
            ]

        type_per_record = decode(type_enc, type_idx)
        seqid_per_record = decode(seqid_enc, seqid_idx)
        strand_per_record = decode(strand_enc, strand_idx, default="+")
        if attr_name is not None and attr_enc is not None:
            attr_per_record = decode(attr_enc, attr_idx)
        else:
            attr_per_record = [None] * n_records

        gene_indices = [i for i, t in enumerate(type_per_record) if t == "gene"]
        if not gene_indices:
            raise StepError(
                "gene_structure: no 'gene' records found in input"
            )

        gene_id_by_index: dict[int, str] = {}
        gene_names: list[str] = []
        for gi in gene_indices:
            raw = attr_per_record[gi]
            gid = parse_gene_id(raw) if raw else None
            if not gid:
                gid = f"gene_{gi}"
            gene_id_by_index[gi] = gid
            gene_names.append(gid)
        gene_set = set(gene_names)

        # transcript -> gene map (GFF3 parent chain).
        transcript_to_gene: dict[str, str] = {}
        for i, t in enumerate(type_per_record):
            if t in ("gene", "exon", "CDS"):
                continue
            raw = attr_per_record[i]
            if not raw:
                continue
            tid = parse_record_id(raw)
            kind, pid = parse_parent(raw)
            if tid and kind == "gene" and pid:
                transcript_to_gene[tid] = pid

        def resolve_parent_gene(raw):
            if not raw:
                return None
            gid = parse_direct_gene_id(raw)
            if gid is not None:
                return gid
            kind, pid = parse_parent(raw)
            if pid is None:
                return None
            if kind == "gene":
                return pid
            return transcript_to_gene.get(pid)

        exons_by_gene: dict[str, list[tuple[float, float]]] = {
            gid: [] for gid in gene_set
        }
        cds_by_gene: dict[str, list[tuple[float, float]]] = {
            gid: [] for gid in gene_set
        }
        fallback_exons: list[int] = []
        fallback_cds: list[int] = []

        for i, t in enumerate(type_per_record):
            if t not in ("exon", "CDS"):
                continue
            gid = resolve_parent_gene(attr_per_record[i])
            if gid is not None:
                if gid in gene_set:
                    target = exons_by_gene if t == "exon" else cds_by_gene
                    target[gid].append((float(starts[i]), float(ends[i])))
            else:
                if t == "exon":
                    fallback_exons.append(i)
                else:
                    fallback_cds.append(i)

        gene_spans = {
            gene_id_by_index[gi]: (
                seqid_per_record[gi],
                float(starts[gi]),
                float(ends[gi]),
            )
            for gi in gene_indices
        }

        def attribute_by_span(i):
            sid = seqid_per_record[i]
            s = float(starts[i])
            e = float(ends[i])
            for gid, (gsid, gs, ge) in gene_spans.items():
                if gsid == sid and s >= gs and e <= ge:
                    return gid
            return None

        for i in fallback_exons:
            gid = attribute_by_span(i)
            if gid is not None:
                exons_by_gene[gid].append((float(starts[i]), float(ends[i])))
        for i in fallback_cds:
            gid = attribute_by_span(i)
            if gid is not None:
                cds_by_gene[gid].append((float(starts[i]), float(ends[i])))

        rows: list[list[float]] = []
        for gi in gene_indices:
            gid = gene_id_by_index[gi]
            s = float(starts[gi])
            e = float(ends[gi])
            strand_name = strand_per_record[gi]
            strand_val = 1.0 if strand_name == "+" else -1.0

            n_exons = len(exons_by_gene[gid])
            n_introns = max(0, n_exons - 1)
            gene_len = e - s + 1.0
            cds_total = sum(ee - es + 1.0 for es, ee in cds_by_gene[gid])
            rows.append([
                float(n_exons), float(n_introns), gene_len,
                cds_total, strand_val,
            ])

        out_data = compact_numeric(np.asarray(rows, dtype=np.float64))

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
            "fallback_exons": len(fallback_exons),
            "fallback_cds": len(fallback_cds),
        }

        print(
            f"[gene_structure] {len(gene_indices)} genes, "
            f"{multi_exon} multi-exon, "
            f"mean_exons={out_data[:, 0].mean():.2f}, "
            f"fallback exon/CDS={len(fallback_exons)}/{len(fallback_cds)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
