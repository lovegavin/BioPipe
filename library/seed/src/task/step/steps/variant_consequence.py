"""Annotate VCF records with the most severe transcript consequence."""
from __future__ import annotations

from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf
from src.task.step.steps._native_results import output_directory, remember_native, result_file
from src.task.step.steps._variant_utils import (
    SEVERITY_RANK,
    annotate_variant,
    load_fasta,
    load_gff3,
)

_INFO_LINES = (
    '##INFO=<ID=CSQ,Number=1,Type=String,Description="Most severe consequence across transcripts (Operon)">',
    '##INFO=<ID=GENE,Number=1,Type=String,Description="Gene name for the most severe consequence">',
    '##INFO=<ID=TX,Number=1,Type=String,Description="Transcript id for the most severe consequence">',
    '##INFO=<ID=AA,Number=1,Type=String,Description="Amino acid change for coding SNVs">',
)


def _file_path(artifact, operator, formats):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    fmt = str(getattr(artifact, "format", ""))
    if formats and fmt not in formats:
        raise StepError(f"{operator} expects format {'/'.join(sorted(formats))}, got {fmt!r}")
    return next(iter(artifact.files.values()))


class VariantConsequenceStep(Step):
    provider = "operon-core"
    parameters_file = "variant_consequence.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "variant_consequence",
        "version": "1.0.0",
        "kind": "operator",
        "title": "variant_consequence",
        "description": "Annotate VCF records with the most severe transcript consequence.",
        "category": "Genome",
        "icon": "Tags",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}}},
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["gff3"]}}},
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["fasta"]}}},
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "vcf"}},
                    "info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 3,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 512 * 1024 * 1024, 8 * 1024 * 1024

    def run(self, ctx: Context, inputs) -> None:
        variants, annotation, reference = inputs
        params = ctx.step_params
        out_name = params.get("output", "annotated") or "annotated"
        max_variants = int(params.get("max_variants", 0) or 0)
        vcf_path = _file_path(variants, "variant_consequence", {"vcf", "vcf.gz"})
        gff_path = _file_path(annotation, "variant_consequence", {"gff3"})
        fasta_path = _file_path(reference, "variant_consequence", {"fasta"})

        genes, transcripts, bins = load_gff3(gff_path)
        genome = load_fasta(fasta_path)
        directory = Path(output_directory(ctx, out_name))
        destination = directory / f"{out_name}.vcf"

        counts = {}
        n_variants = 0
        n_annotated = 0
        n_written = 0
        with vcf.open_text(vcf_path) as stream:
            meta, samples, _ = vcf.read_header(stream)
            with open(destination, "w", encoding="utf-8", newline="\n") as out:
                for line in meta:
                    out.write(line + "\n")
                for line in _INFO_LINES:
                    out.write(line + "\n")
                columns = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
                if samples:
                    columns.append("FORMAT")
                    columns.extend(samples)
                out.write("\t".join(columns) + "\n")
                for fixed, rest in vcf.iter_sites(stream):
                    n_variants += 1
                    if max_variants and n_variants > max_variants:
                        break
                    chrom, pos_text, ident, ref, alt_text, qual, filt, info = fixed
                    pos = int(pos_text)
                    best = None
                    for alt in alt_text.split(","):
                        if alt in (".", "*"):
                            continue
                        result = annotate_variant(chrom, pos, ref, alt, bins, genes, genome)
                        if result[0] == "intergenic":
                            continue
                        rank = SEVERITY_RANK.get(result[0], 99)
                        if best is None or rank < best[0]:
                            best = (rank,) + result
                    if best is None:
                        consequence, gene, tx, aa = "intergenic", "", "", ""
                    else:
                        consequence, gene, tx, aa = best[1], best[2], best[3], best[4] or ""
                        n_annotated += 1
                    counts[consequence] = counts.get(consequence, 0) + 1
                    extra = f"CSQ={consequence}"
                    if gene:
                        extra += f";GENE={gene}"
                    if tx:
                        extra += f";TX={tx}"
                    if aa:
                        extra += f";AA={aa}"
                    new_info = (info + ";" + extra) if info not in ("", ".") else extra
                    row = [chrom, pos_text, ident, ref, alt_text, qual, filt, new_info]
                    if rest:
                        row.extend(rest.split("\t"))
                    out.write("\t".join(row) + "\n")
                    n_written += 1

        size = int(destination.stat().st_size)
        result_files = [result_file("annotated", str(destination), "vcf", "Annotated VCF")]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "vcf",
            {"annotated": str(destination)},
            info={"representation": "vcf", "source": "variant_consequence"},
        )
        self._result_files = result_files
        self._export_data = {
            "n_variants": n_variants,
            "n_annotated": n_annotated,
            "n_written": n_written,
            "n_genes": len(genes),
            "n_transcripts": len(transcripts),
            "counts": counts,
            "file": str(destination),
            "bytes": size,
            "result_files": result_files,
        }
        print(f"[variant_consequence] {n_written} records, {n_annotated} annotated")

    def export(self, ctx: Context) -> dict:
        return dict(getattr(self, "_export_data", {}))
