set -e

echo "########## 1. 写入源码 / route / demo / verify ##########"

mkdir -p src/task/step/steps

cat > src/task/step/steps/_annotation_columns.py << 'PYEOF'
"""Column-role resolution for GFF3/GTF annotation operators.

GFF3 and GTF share the same 9-column layout and record semantics,
but name the columns differently:

    role        GFF3         GTF
    ----------  -----------  -----------
    seqid       seqid        seqname
    type        type         feature
    attributes  attributes   attribute

Operators resolve their required columns by role so the same body
works on Forms produced by either reader. Attribute parsing accepts
both GTF ``key "value";`` and GFF3 ``key=value;`` syntaxes.
"""
from __future__ import annotations

import re

from src.core import StepError


ROLE_ALIASES = {
    "seqid": ("seqid", "seqname"),
    "type": ("type", "feature"),
    "attributes": ("attributes", "attribute"),
    "start": ("start",),
    "end": ("end",),
    "strand": ("strand",),
    "score": ("score",),
    "source": ("source",),
    "phase": ("phase", "frame"),
}


_GENE_ID_PATTERNS = (
    re.compile(r'\bgene_id\s*"([^"]+)"'),
    re.compile(r'\bgene_id\s*=\s*([^;]+)'),
    re.compile(r'\bID\s*=\s*([^;,]+)'),
)


def require_role(labels, encoders, role, step_name, require_encoder=True):
    aliases = ROLE_ALIASES[role]
    for alias in aliases:
        if alias in labels:
            encoder = encoders.get(alias)
            if require_encoder and encoder is None:
                raise StepError(
                    f"{step_name}: '{alias}' column is not encoded"
                )
            return alias, labels[alias], encoder
    raise StepError(
        f"{step_name}: no '{role}' label found. "
        f"Tried aliases {list(aliases)}, "
        f"available columns {sorted(labels)}"
    )


def try_role(labels, encoders, role):
    for alias in ROLE_ALIASES[role]:
        if alias in labels:
            return alias, labels[alias], encoders.get(alias)
    return None, None, None


def parse_gene_id(attributes):
    if not attributes:
        return None
    for pattern in _GENE_ID_PATTERNS:
        match = pattern.search(attributes)
        if match:
            value = match.group(1).strip()
            if ":" in value:
                value = value.split(":", 1)[1]
            return value
    return None
PYEOF


cat > src/task/step/steps/gff_feature_stats.py << 'PYEOF'
"""Per-feature-type statistics for any GFF3/GTF Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_columns import require_role


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
        encoders = form.info.get("encoders", {}).get(fld_dim, {})

        _, type_idx, type_enc = require_role(
            fld_labels, encoders, "type", "gff_feature_stats",
        )
        _, start_idx, _ = require_role(
            fld_labels, encoders, "start", "gff_feature_stats",
            require_encoder=False,
        )
        _, end_idx, _ = require_role(
            fld_labels, encoders, "end", "gff_feature_stats",
            require_encoder=False,
        )

        type_codes = form.data[:, type_idx]
        starts = form.data[:, start_idx]
        ends = form.data[:, end_idx]

        lengths = ends - starts + 1.0

        type_names = sorted({
            type_enc.inverse[int(round(float(c)))]
            for c in np.unique(type_codes)
        })

        n_types = len(type_names)
        out_data = np.zeros((n_types, len(_STAT_LABELS)), dtype=np.float32)

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
PYEOF


cat > src/task/step/steps/gene_structure.py << 'PYEOF'
"""Per-gene structure summary for any GFF3 / GTF Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_columns import parse_gene_id, require_role, try_role


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

        type_codes = form.data[:, type_idx]
        seqid_codes = form.data[:, seqid_idx]
        starts = form.data[:, start_idx].astype(np.float64)
        ends = form.data[:, end_idx].astype(np.float64)
        strand_codes = form.data[:, strand_idx]

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

        def gene_name(i):
            if attr_name is not None and attr_enc is not None:
                code = int(round(float(form.data[i, attr_idx])))
                raw = attr_enc.inverse.get(code, "")
                parsed = parse_gene_id(str(raw))
                if parsed:
                    return parsed
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
PYEOF


cat > src/task/step/steps/annotation_gaps.py << 'PYEOF'
"""Inter-gene gap statistics for any GFF3/GTF Form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
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
PYEOF


mkdir -p routes/gtf_annotation
cat > routes/gtf_annotation/route.json << 'JSONEOF'
{"key": "gtf_annotation", "name": "GTF Annotation Analysis"}
JSONEOF

cat > routes/gtf_annotation/task.yaml << 'YAMLEOF'
name: gtf_annotation

sources:
  annot:
    path: input/saccharomyces_cerevisiae.gtf.gz
    dims: [record, field]
    labels:
      record: auto
      field: builtin

steps:
  - name: gff_feature_stats
    inputs: [annot]
    params: {output: stats}

  - name: describe
    inputs: [stats]

  - name: gene_structure
    inputs: [annot]
    params: {output: structures}

  - name: describe
    inputs: [structures]

  - name: annotation_gaps
    inputs: [annot]
    params: {min_gap: 500, output: gaps}

  - name: describe
    inputs: [gaps]

  - name: histogram
    inputs: [structures]
    params:
      dim: statistic
      value_label: n_exons
      bins: 30
      filename: exon_count_hist.png
      title: "Exons per gene (S. cerevisiae GTF)"
      xlabel: "Exon count"

  - name: histogram
    inputs: [gaps]
    params:
      dim: statistic
      value_label: gap_length
      bins: 40
      filename: gap_length_hist.png
      title: "Inter-gene gap lengths (>= 500 bp)"
      xlabel: "Gap length (bp)"
YAMLEOF


mkdir -p tasks/gtf_annotation_demo/input

cat > tasks/gtf_annotation_demo/task.yaml << 'YAMLEOF'
name: gtf_annotation_demo

sources:
  annot:
    path: input/saccharomyces_cerevisiae.gtf.gz
    dims: [record, field]
    labels:
      record: auto
      field: builtin

steps:
  - name: gff_feature_stats
    inputs: [annot]
    params: {output: stats}

  - name: describe
    inputs: [stats]

  - name: gene_structure
    inputs: [annot]
    params: {output: structures}

  - name: describe
    inputs: [structures]

  - name: annotation_gaps
    inputs: [annot]
    params: {min_gap: 500, output: gaps}

  - name: describe
    inputs: [gaps]

  - name: histogram
    inputs: [structures]
    params:
      dim: statistic
      value_label: n_exons
      bins: 30
      filename: exon_count_hist.png
      title: "Exons per gene (S. cerevisiae GTF)"
      xlabel: "Exon count"

  - name: histogram
    inputs: [gaps]
    params:
      dim: statistic
      value_label: gap_length
      bins: 40
      filename: gap_length_hist.png
      title: "Inter-gene gap lengths (>= 500 bp)"
      xlabel: "Gap length (bp)"
YAMLEOF

cat > tasks/gtf_annotation_demo/download.sh << 'SHEOF'
#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR/input"

BASE="https://ftp.ensembl.org/pub/release-110"

if [ ! -s saccharomyces_cerevisiae.gtf.gz ]; then
  curl -fL -o saccharomyces_cerevisiae.gtf.gz \
    "$BASE/gtf/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.110.gtf.gz"
fi

if [ ! -s saccharomyces_cerevisiae.gff3.gz ]; then
  curl -fL -o saccharomyces_cerevisiae.gff3.gz \
    "$BASE/gff3/saccharomyces_cerevisiae/Saccharomyces_cerevisiae.R64-1-1.110.gff3.gz"
fi

ls -lh
SHEOF
chmod +x tasks/gtf_annotation_demo/download.sh


cat > tasks/gtf_annotation_demo/test_gtf_annotation.py << 'PYEOF'
"""Standalone verification of GFF3/GTF annotation operators."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.task.step.steps.gff_feature_stats import GffFeatureStatsStep
from src.task.step.steps.gene_structure import GeneStructureStep
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from biopipe_sdk.testing import run_operator


GTF_BODY = (
    'chrI\tensembl\tgene\t1\t500\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tmRNA\t1\t500\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\texon\t1\t200\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\texon\t300\t500\t.\t+\t.\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tCDS\t50\t200\t.\t+\t0\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tCDS\t300\t500\t.\t+\t0\tgene_id "GENE1"; transcript_id "GENE1_mRNA";\n'
    'chrI\tensembl\tgene\t1000\t1500\t.\t-\t.\tgene_id "GENE2"; transcript_id "GENE2_mRNA";\n'
    'chrI\tensembl\tmRNA\t1000\t1500\t.\t-\t.\tgene_id "GENE2"; transcript_id "GENE2_mRNA";\n'
    'chrI\tensembl\texon\t1000\t1500\t.\t-\t.\tgene_id "GENE2"; transcript_id "GENE2_mRNA";\n'
)

GFF3_BODY = (
    '##gff-version 3\n'
    'chrI\tensembl\tgene\t1\t500\t.\t+\t.\tID=gene:GENE1;biotype=protein_coding\n'
    'chrI\tensembl\tmRNA\t1\t500\t.\t+\t.\tID=GENE1_mRNA;Parent=gene:GENE1\n'
    'chrI\tensembl\texon\t1\t200\t.\t+\t.\tID=GENE1_exon1;Parent=GENE1_mRNA\n'
    'chrI\tensembl\texon\t300\t500\t.\t+\t.\tID=GENE1_exon2;Parent=GENE1_mRNA\n'
    'chrI\tensembl\tCDS\t50\t200\t.\t+\t0\tID=GENE1_CDS1;Parent=GENE1_mRNA\n'
    'chrI\tensembl\tCDS\t300\t500\t.\t+\t0\tID=GENE1_CDS2;Parent=GENE1_mRNA\n'
    'chrI\tensembl\tgene\t1000\t1500\t.\t-\t.\tID=gene:GENE2;biotype=protein_coding\n'
    'chrI\tensembl\tmRNA\t1000\t1500\t.\t-\t.\tID=GENE2_mRNA;Parent=gene:GENE2\n'
    'chrI\tensembl\texon\t1000\t1500\t.\t-\t.\tID=GENE2_exon1;Parent=GENE2_mRNA\n'
)


def _write_gtf(tmpdir, body, name="test.gtf", newline="\n"):
    path = Path(tmpdir) / name
    path.write_text(body.replace("\n", newline), encoding="utf-8")
    return path


def _read_gtf(tmpdir, body, newline="\n"):
    path = _write_gtf(tmpdir, body, newline=newline)
    return read_source(
        path,
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _read_gff3(tmpdir, body):
    path = Path(tmpdir) / "test.gff3"
    path.write_text(body, encoding="utf-8")
    return read_source(
        path,
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _forms_equal(a, b):
    if a.dims != b.dims:
        return False
    if a.labels != b.labels:
        return False
    if a.data.shape != b.data.shape:
        return False
    if not np.allclose(a.data, b.data, equal_nan=True):
        return False
    return True


def _stat(out, feature, stat):
    i = out.labels["feature_type"][feature]
    j = out.labels["statistic"][stat]
    return float(out.data[i, j])


def test_gtf_reader_lf_crlf_consistent():
    with TemporaryDirectory() as d:
        lf = _read_gtf(d, GTF_BODY, newline="\n")
        crlf = _read_gtf(d, GTF_BODY, newline="\r\n")
        assert _forms_equal(lf, crlf), "LF and CRLF GTF must produce identical Forms"
    print("  gtf reader LF/CRLF consistent          ok")


def test_gff_feature_stats_hand_counted_gtf():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    out = run_operator(GffFeatureStatsStep, [form], {})

    assert out.dims == ["feature_type", "statistic"]
    assert _stat(out, "gene", "count") == 2.0
    assert _stat(out, "gene", "total_length") == 1001.0
    assert np.isclose(_stat(out, "gene", "mean_length"), 500.5)
    assert _stat(out, "gene", "min_length") == 500.0
    assert _stat(out, "gene", "max_length") == 501.0
    assert _stat(out, "gene", "mean_exons_per_gene") == 1.5

    assert _stat(out, "exon", "count") == 3.0
    assert _stat(out, "exon", "total_length") == 902.0
    assert np.isclose(_stat(out, "exon", "mean_length"), 902.0 / 3.0)
    assert _stat(out, "exon", "min_length") == 200.0
    assert _stat(out, "exon", "max_length") == 501.0

    assert _stat(out, "CDS", "count") == 2.0
    assert _stat(out, "CDS", "total_length") == 352.0
    assert np.isclose(_stat(out, "CDS", "mean_length"), 176.0)
    print("  gff_feature_stats on GTF hand-counted  ok")


def test_gene_structure_hand_counted_gtf():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    out = run_operator(GeneStructureStep, [form], {})

    assert out.dims == ["gene", "statistic"]
    assert set(out.labels["gene"]) == {"GENE1", "GENE2"}

    i = out.labels["gene"]["GENE1"]
    assert float(out.data[i, out.labels["statistic"]["n_exons"]]) == 2.0
    assert float(out.data[i, out.labels["statistic"]["n_introns"]]) == 1.0
    assert float(out.data[i, out.labels["statistic"]["gene_length"]]) == 500.0
    assert float(out.data[i, out.labels["statistic"]["cds_total"]]) == 352.0
    assert float(out.data[i, out.labels["statistic"]["strand"]]) == 1.0

    j = out.labels["gene"]["GENE2"]
    assert float(out.data[j, out.labels["statistic"]["n_exons"]]) == 1.0
    assert float(out.data[j, out.labels["statistic"]["n_introns"]]) == 0.0
    assert float(out.data[j, out.labels["statistic"]["gene_length"]]) == 501.0
    assert float(out.data[j, out.labels["statistic"]["cds_total"]]) == 0.0
    assert float(out.data[j, out.labels["statistic"]["strand"]]) == -1.0
    print("  gene_structure on GTF hand-counted     ok")


def test_annotation_gaps_hand_counted_gtf():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    out = run_operator(AnnotationGapsStep, [form], {})

    assert out.dims == ["gap", "statistic"]
    assert out.data.shape == (1, 5)
    assert float(out.data[0, out.labels["statistic"]["gap_length"]]) == 499.0
    assert float(out.data[0, out.labels["statistic"]["left_start"]]) == 1.0
    assert float(out.data[0, out.labels["statistic"]["left_end"]]) == 500.0
    assert float(out.data[0, out.labels["statistic"]["right_start"]]) == 1000.0
    assert float(out.data[0, out.labels["statistic"]["right_end"]]) == 1500.0
    assert out.info["seqid"] == ["chrI"]
    assert out.info["left_gene"] == ["chrI:1-500"]
    assert out.info["right_gene"] == ["chrI:1000-1500"]
    print("  annotation_gaps on GTF hand-counted    ok")


def test_gtf_gff3_equivalent_outputs():
    with TemporaryDirectory() as d:
        gtf_form = _read_gtf(d, GTF_BODY)
        gff3_form = _read_gff3(d, GFF3_BODY)

    fs_gtf = run_operator(GffFeatureStatsStep, [gtf_form], {})
    fs_gff3 = run_operator(GffFeatureStatsStep, [gff3_form], {})
    assert set(fs_gtf.labels["feature_type"]) == set(fs_gff3.labels["feature_type"])
    for t in fs_gtf.labels["feature_type"]:
        for s in fs_gtf.labels["statistic"]:
            a = _stat(fs_gtf, t, s)
            b = _stat(fs_gff3, t, s)
            assert np.isclose(a, b), f"gff_feature_stats mismatch {t}/{s}: {a} vs {b}"

    gs_gtf = run_operator(GeneStructureStep, [gtf_form], {})
    gs_gff3 = run_operator(GeneStructureStep, [gff3_form], {})
    assert set(gs_gtf.labels["gene"]) == set(gs_gff3.labels["gene"])
    for g in gs_gtf.labels["gene"]:
        i = gs_gtf.labels["gene"][g]
        j = gs_gff3.labels["gene"][g]
        for s in gs_gtf.labels["statistic"]:
            a = float(gs_gtf.data[i, gs_gtf.labels["statistic"][s]])
            b = float(gs_gff3.data[j, gs_gff3.labels["statistic"][s]])
            assert np.isclose(a, b), f"gene_structure mismatch {g}/{s}: {a} vs {b}"

    ag_gtf = run_operator(AnnotationGapsStep, [gtf_form], {})
    ag_gff3 = run_operator(AnnotationGapsStep, [gff3_form], {})
    assert ag_gtf.data.shape == ag_gff3.data.shape
    assert ag_gtf.info["seqid"] == ag_gff3.info["seqid"]
    assert ag_gtf.info["left_gene"] == ag_gff3.info["left_gene"]
    assert ag_gtf.info["right_gene"] == ag_gff3.info["right_gene"]
    assert np.allclose(ag_gtf.data, ag_gff3.data, equal_nan=True)
    print("  GTF / GFF3 outputs identical           ok")


def test_wrong_representation_rejected():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    labels = dict(form.labels)
    fields = dict(labels["field"])
    fields.pop("feature")
    labels["field"] = fields
    bad = Form(data=form.data[:, :1], dims=form.dims, labels=labels,
               info=form.info)
    try:
        run_operator(GffFeatureStatsStep, [bad], {})
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "no 'type' label" in str(exc), str(exc)
    print("  missing feature-type column rejected   ok")


def test_missing_encoder_rejected():
    with TemporaryDirectory() as d:
        form = _read_gtf(d, GTF_BODY)
    encoders = dict(form.info["encoders"]["field"])
    encoders.pop("feature")
    form.info["encoders"]["field"] = encoders
    try:
        run_operator(GffFeatureStatsStep, [form], {})
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "not encoded" in str(exc), str(exc)
    print("  missing feature encoder rejected       ok")


def main():
    print("gtf_annotation verification")
    test_gtf_reader_lf_crlf_consistent()
    test_gff_feature_stats_hand_counted_gtf()
    test_gene_structure_hand_counted_gtf()
    test_annotation_gaps_hand_counted_gtf()
    test_gtf_gff3_equivalent_outputs()
    test_wrong_representation_rejected()
    test_missing_encoder_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
PYEOF


cat > tasks/verify_gtf_annotation.py << 'PYEOF'
"""External-baseline verification of the GFF3/GTF annotation operators."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import StepError
from src.reader import read_source
from src.task.step.steps.gff_feature_stats import GffFeatureStatsStep
from src.task.step.steps.gene_structure import GeneStructureStep
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:60], str(actual)[:60]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


SGD_CHR_LENGTHS = {
    "I": 230218, "II": 813184, "III": 316620, "IV": 1531933,
    "V": 576874, "VI": 270161, "VII": 1090946, "VIII": 562643,
    "IX": 439888, "X": 745751, "XI": 666816, "XII": 1078177,
    "XIII": 924431, "XIV": 784333, "XV": 1091291, "XVI": 948066,
    "Mito": 85779,
}


def _read(path):
    return read_source(
        Path(path),
        dims=["record", "field"],
        labels={"record": "auto", "field": "builtin"},
    )


def _feat_count(out, feature):
    if feature not in out.labels["feature_type"]:
        return 0
    i = out.labels["feature_type"][feature]
    j = out.labels["statistic"]["count"]
    return int(round(float(out.data[i, j])))


def main():
    gtf_path = Path("tasks/gtf_annotation_demo/input/saccharomyces_cerevisiae.gtf.gz")
    gff3_path = Path("tasks/gtf_annotation_demo/input/saccharomyces_cerevisiae.gff3.gz")

    if not gtf_path.exists():
        print(f"missing {gtf_path}. Run tasks/gtf_annotation_demo/download.sh first.")
        sys.exit(1)
    if not gff3_path.exists():
        print(f"missing {gff3_path}. Run tasks/gtf_annotation_demo/download.sh first.")
        sys.exit(1)

    section("1. GTF reader - chromosome set matches SGD R64-1-1")
    gtf = _read(gtf_path)
    seqid_col = "seqname" if "seqname" in gtf.labels["field"] else "seqid"
    enc = gtf.info["encoders"]["field"][seqid_col]
    chroms = sorted({enc.inverse[int(round(float(c)))]
                     for c in gtf.data[:, gtf.labels["field"][seqid_col]]})
    record("chromosome count == 17 (SGD)", len(chroms) == 17, 17, len(chroms))
    record("chr I present", "I" in chroms, "I in set", "I" in chroms)
    record("chr XVI present", "XVI" in chroms, "XVI in set", "XVI" in chroms)
    record("Mito present", "Mito" in chroms, "Mito in set", "Mito" in chroms)

    section("2. gene_structure - chromosome coordinates within SGD lengths")
    gs = run_operator(GeneStructureStep, [gtf], {})

    type_col = "feature" if "feature" in gtf.labels["field"] else "type"
    type_enc = gtf.info["encoders"]["field"][type_col]
    type_codes = gtf.data[:, gtf.labels["field"][type_col]]
    starts = gtf.data[:, gtf.labels["field"]["start"]]
    ends = gtf.data[:, gtf.labels["field"]["end"]]
    seq_codes = gtf.data[:, gtf.labels["field"][seqid_col]]

    max_end_by_chr = {}
    for i in range(gtf.data.shape[0]):
        if type_enc.inverse[int(round(float(type_codes[i])))] != "gene":
            continue
        sid = enc.inverse[int(round(float(seq_codes[i])))]
        max_end_by_chr[sid] = max(max_end_by_chr.get(sid, 0.0), float(ends[i]))

    ok_all = True
    for sid, mx in max_end_by_chr.items():
        limit = SGD_CHR_LENGTHS.get(sid)
        if limit is not None and mx > limit:
            ok_all = False
    record("all gene ends <= SGD chromosome length", ok_all, True, ok_all)

    section("3. gff_feature_stats - Ensembl release 110 known counts")
    fs_gtf = run_operator(GffFeatureStatsStep, [gtf], {})
    n_genes = _feat_count(fs_gtf, "gene")
    n_exons = _feat_count(fs_gtf, "exon")
    record("gene count in [6600, 7300] (SGD/Ensembl)",
            6600 <= n_genes <= 7300, "6600..7300", n_genes)
    record("exon count > gene count", n_exons > n_genes, ">n_genes", n_exons)
    record("CDS count > 0", _feat_count(fs_gtf, "CDS") > 0,
            ">0", _feat_count(fs_gtf, "CDS"))

    section("4. Cross-format consistency GTF vs GFF3 (same Ensembl annotation)")
    gff3 = _read(gff3_path)
    fs_gff3 = run_operator(GffFeatureStatsStep, [gff3], {})

    for feat in ("gene", "mRNA", "exon", "CDS"):
        a = _feat_count(fs_gtf, feat)
        b = _feat_count(fs_gff3, feat)
        record(f"{feat} count equal across formats", a == b, a, b)

    gs_gff3 = run_operator(GeneStructureStep, [gff3], {})

    gtf_genes = gs.labels["gene"]
    gff3_genes = gs_gff3.labels["gene"]
    common = sorted(set(gtf_genes) & set(gff3_genes))
    mismatches = 0
    for g in common:
        i = gtf_genes[g]
        j = gff3_genes[g]
        if float(gs.data[i, gs.labels["statistic"]["n_exons"]]) != \
           float(gs_gff3.data[j, gs_gff3.labels["statistic"]["n_exons"]]):
            mismatches += 1
        if float(gs.data[i, gs.labels["statistic"]["gene_length"]]) != \
           float(gs_gff3.data[j, gs_gff3.labels["statistic"]["gene_length"]]):
            mismatches += 1
    record("per-gene n_exons and gene_length equal",
            mismatches == 0 and len(common) > 5000,
            "0 mismatches, >5000 genes",
            f"{mismatches} mismatches, {len(common)} genes")

    ag_gtf = run_operator(AnnotationGapsStep, [gtf], {"min_gap": 500})
    ag_gff3 = run_operator(AnnotationGapsStep, [gff3], {"min_gap": 500})
    record("annotation_gaps shapes equal",
            ag_gtf.data.shape == ag_gff3.data.shape,
            ag_gtf.data.shape, ag_gff3.data.shape)
    record("annotation_gaps gap_length arrays equal",
            np.allclose(ag_gtf.data[:, 0], ag_gff3.data[:, 0], equal_nan=True),
            "allclose", "not allclose")

    section("5. Negative cases")
    import copy
    bad = copy.deepcopy(gtf)
    encs = dict(bad.info["encoders"]["field"])
    encs.pop(type_col)
    bad.info["encoders"]["field"] = encs
    try:
        run_operator(GffFeatureStatsStep, [bad], {})
        record("missing feature encoder raises StepError", False, "StepError", "no error")
    except StepError:
        record("missing feature encoder raises StepError", True, "StepError", "StepError")
    except Exception as exc:
        record("missing feature encoder raises StepError", False, "StepError", type(exc).__name__)

    ag_huge = run_operator(AnnotationGapsStep, [gtf], {"min_gap": 10**9})
    record("min_gap 1e9 yields empty gaps", ag_huge.data.shape[0] == 0,
            0, ag_huge.data.shape[0])

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<56}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, expected, actual in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<56}{expected:>12}{actual:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF


echo
echo "########## 2. registry build ##########"
python -m biopipe registry build

echo
echo "########## 3. download real Ensembl data ##########"
bash tasks/gtf_annotation_demo/download.sh

echo
echo "########## 4. run gtf_annotation_demo ##########"
python scripts/run.py tasks/gtf_annotation_demo

echo
echo "########## 5. standalone demo test ##########"
python tasks/gtf_annotation_demo/test_gtf_annotation.py

echo
echo "########## 6. external-reference verification ##########"
python tasks/verify_gtf_annotation.py

echo
echo "########## 7. regression: existing GFF3/GTF demos ##########"
for d in tasks/gff_feature_stats_demo tasks/gene_structure_demo tasks/annotation_gaps_demo tasks/gff3_demo tasks/gtf_demo; do
    echo "--- $d ---"
    if python scripts/run.py "$d" > /dev/null 2>&1; then echo "ok"; else echo "FAILED"; fi
done

echo
echo "########## 8. regression: existing pytest fixtures ##########"
if python -c "import pytest" > /dev/null 2>&1; then
    python -m pytest -q \
      tasks/gff_feature_stats_demo/test_gff_feature_stats.py \
      tasks/gene_structure_demo/test_gene_structure.py \
      tasks/annotation_gaps_demo/test_annotation_gaps.py || true
else
    echo "pytest not installed, skipping"
fi

echo
echo "########## DONE ##########"
