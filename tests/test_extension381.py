"""Variant consequence annotation operator tests (extension 381)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core import FileArtifact, StepError
from src.task.step.steps._variant_utils import (
    annotate_variant,
    coding_snv,
    load_fasta,
    load_gff3,
    parse_attributes,
    _splice_class,
)
from src.task.step.steps.coding_variant_filter import CodingVariantFilterStep
from src.task.step.steps.variant_consequence import VariantConsequenceStep
from src.task.step.steps.variant_impact_summary import VariantImpactSummaryStep


_GENOME = (
    "CCCATGGAATTTGGGCCCAAATTTGATTAA"      # 1-30: ATG GAA TTT GGG CCC AAA TTT GAT TAA
    "ACGTACGTACGTACGTACGTACGTACGTAC"       # 31-60
    "TTTTACGTAA"                            # 61-70 intron
    "GGGGCCCCAAAATTTTGGGG"                 # 71-90
    "ACGTACGTACGTACGTACGT"                 # 91-110
)

_GFF = """##gff-version 3
chr1\t.\tgene\t1\t30\t.\t+\t.\tID=gene1;Name=GENE1;biotype=protein_coding
chr1\t.\tmRNA\t1\t30\t.\t+\t.\tID=tx1;Parent=gene1;biotype=protein_coding
chr1\t.\texon\t1\t30\t.\t+\t.\tID=ex1;Parent=tx1
chr1\t.\tCDS\t4\t30\t.\t+\t0\tID=cds1;Parent=tx1
chr1\t.\tgene\t31\t90\t.\t+\t.\tID=gene2;Name=GENE2;biotype=lncRNA
chr1\t.\tmRNA\t31\t90\t.\t+\t.\tID=tx2;Parent=gene2;biotype=lncRNA
chr1\t.\texon\t31\t60\t.\t+\t.\tID=ex2;Parent=tx2
chr1\t.\texon\t71\t90\t.\t+\t.\tID=ex3;Parent=tx2
"""

_VCF = """##fileformat=VCFv4.2
##contig=<ID=chr1,length=110>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
chr1\t7\t.\tG\tT\t.\t.\t.
chr1\t15\t.\tG\tA\t.\t.\t.
chr1\t61\t.\tA\tC\t.\t.\t.
chr1\t65\t.\tA\tG\t.\t.\t.
chr1\t100\t.\tA\tG\t.\t.\t.
"""


class Ctx(dict):
    def __init__(self, params, root=None):
        super().__init__()
        self.step_params = dict(params)
        self._root = root

    def artifact_path(self, name):
        return str(self._root / name)


@pytest.fixture()
def fixture_paths(tmp_path):
    fasta = tmp_path / "genome.fa"
    fasta.write_text(">chr1\n" + _GENOME + "\n", encoding="utf-8")
    gff = tmp_path / "annotation.gff3"
    gff.write_text(_GFF, encoding="utf-8")
    vcf = tmp_path / "variants.vcf"
    vcf.write_text(_VCF, encoding="utf-8")
    return fasta, gff, vcf


def _artifacts(fixture_paths):
    fasta, gff, vcf = fixture_paths
    return (
        FileArtifact("vcf", {"variants": str(vcf)}),
        FileArtifact("gff3", {"annotation": str(gff)}),
        FileArtifact("fasta", {"reference": str(fasta)}),
    )


def test_parse_attributes_and_load_gff3(fixture_paths):
    assert parse_attributes("ID=tx1;Parent=gene1") == {"ID": "tx1", "Parent": "gene1"}
    _fasta, gff, _vcf = fixture_paths
    genes, transcripts, bins = load_gff3(str(gff))
    assert set(transcripts) == {"tx1", "tx2"}
    assert transcripts["tx1"].is_coding is True
    assert transcripts["tx2"].is_coding is False
    assert transcripts["tx1"].gene_name == "GENE1"
    assert transcripts["tx2"].exons == [(31, 60), (71, 90)]
    assert bins


def test_coding_snv_missense_synonymous_stop(fixture_paths):
    fasta, gff, _vcf = fixture_paths
    import src.task.step.steps._variant_utils as utils

    _genes, transcripts, _bins = load_gff3(str(gff))
    genome = utils.load_fasta(str(fasta))
    tx = transcripts["tx1"]
    assert coding_snv(tx, 7, "T", genome)[0] == "stop_gained"
    assert coding_snv(tx, 15, "A", genome)[0] == "synonymous"
    missense = coding_snv(tx, 16, "A", genome)
    assert missense[0] == "missense"
    assert ">" in missense[1]


def test_splice_and_annotate(fixture_paths):
    fasta, gff, _vcf = fixture_paths
    genes, transcripts, bins = load_gff3(str(gff))
    genome = load_fasta(str(fasta))
    assert _splice_class(transcripts["tx2"], 61) == "splice_donor"
    assert _splice_class(transcripts["tx2"], 65) == "intron"
    consequence, gene, tx, _aa, _dna = annotate_variant("chr1", 7, "G", "T", bins, genes, genome)
    assert consequence == "stop_gained"
    assert gene == "GENE1" and tx == "tx1"
    assert annotate_variant("chr1", 100, "A", "G", bins, genes, genome)[0] == "intergenic"


def test_variant_consequence_operator(fixture_paths, tmp_path):
    ctx = Ctx({"output": "annotated"}, tmp_path)
    step = VariantConsequenceStep()
    step.run(ctx, list(_artifacts(fixture_paths)))
    artifact = ctx["annotated"]
    assert artifact.format == "vcf"
    text = Path(artifact.files["annotated"]).read_text(encoding="utf-8")
    assert "CSQ=stop_gained" in text
    assert "CSQ=synonymous" in text
    assert "CSQ=splice_donor" in text
    assert "CSQ=intergenic" in text
    exported = step.export(ctx)
    assert exported["n_variants"] == 5
    assert exported["n_annotated"] == 4
    assert exported["counts"]["stop_gained"] == 1
    assert exported["result_files"][0]["format"] == "vcf"


def test_coding_filter_operator(fixture_paths, tmp_path):
    annotation_ctx = Ctx({"output": "annotated"}, tmp_path)
    annotate = VariantConsequenceStep()
    annotate.run(annotation_ctx, list(_artifacts(fixture_paths)))
    step = CodingVariantFilterStep()
    ctx = Ctx({"output": "filtered"}, tmp_path)
    step.run(ctx, [annotation_ctx["annotated"]])
    text = Path(ctx["filtered"].files["filtered"]).read_text(encoding="utf-8")
    records = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert sum("CSQ=" in line for line in records) == 3
    assert "CSQ=intron" not in text
    assert step.export(ctx)["kept"] == 3


def test_impact_summary_operator(fixture_paths, tmp_path):
    ctx = Ctx({"output": "annotation"}, tmp_path)
    step = VariantConsequenceStep()
    step.run(ctx, list(_artifacts(fixture_paths)))
    summary_ctx = Ctx({"output": "summary"})
    summary = VariantImpactSummaryStep()
    summary.run(summary_ctx, [ctx["annotation"]])
    form = summary_ctx["summary"]
    assert form.dims == ["consequence", "statistic"]
    assert form.data.shape[1] == 2
    assert summary.export(summary_ctx)["total"] == 5


def test_reader_passes_through(fixture_paths):
    from src.reader.readers.gff_file_reader import GffFileReader

    _fasta, gff, _vcf = fixture_paths
    artifact = GffFileReader().read(str(gff), ["file"], {})
    assert artifact.format == "gff3"
