import shutil

import numpy as np
import pytest

from src.core import StepError
from src.task.step.base import Form
from src.task.step.steps import genome_alignment_stats as stats_module
from src.task.step.steps import genome_rearrangement_summary as rearrangement_module
from src.task.step.steps import genome_synteny_blocks as synteny_module
from src.task.step.steps._genome_align_utils import (
    alignment_statistics,
    chain_blocks,
    rearrangement_summary,
    write_fasta,
)


def _fasta(sequence, name="chr"):
    data = np.array([list(sequence)], dtype="<U1")
    labels = {
        "sequence": {name: 0},
        "position": {str(index): index for index in range(len(sequence))},
    }
    form = Form(data, dims=["sequence", "position"], labels=labels,
                info={"sequences": [sequence]})
    form.validate()
    return form


def _record(reference, reference_start, reference_end, query, query_start, query_end, strand="+", identity=0.98):
    length = abs(reference_end - reference_start)
    return {
        "query": query, "query_length": 100000,
        "query_start": query_start, "query_end": query_end, "strand": strand,
        "reference": reference, "reference_length": 100000,
        "reference_start": reference_start, "reference_end": reference_end,
        "matches": int(length * identity), "block_length": length,
        "mapq": 60, "tags": {}, "identity": identity,
    }


class _Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def test_chain_blocks_merges_colinear_records():
    records = [
        _record("ref", 0, 5000, "qry", 0, 5000),
        _record("ref", 5000, 10000, "qry", 5000, 10000),
        _record("ref", 40000, 46000, "qry", 15000, 21000),
    ]
    blocks = chain_blocks(records, min_block=1000)
    assert len(blocks) == 2
    assert blocks[0]["aligned_bp"] == 10000
    assert blocks[0]["n_alignments"] == 2
    assert blocks[1]["reference_start"] == 40000


def test_chain_blocks_splits_on_strand_flip():
    records = [
        _record("ref", 0, 5000, "qry", 0, 5000, strand="+"),
        _record("ref", 5000, 10000, "qry", 9000, 4000, strand="-"),
    ]
    blocks = chain_blocks(records, min_block=1000)
    assert len(blocks) == 2
    assert {block["strand"] for block in blocks} == {"+", "-"}


def test_rearrangement_summary_counts_breakpoints():
    blocks = [
        {"reference": "ref", "query": "q1", "reference_start": 0, "reference_end": 5000,
         "query_start": 0, "query_end": 5000, "strand": "+", "aligned_bp": 5000},
        {"reference": "ref", "query": "q1", "reference_start": 5000, "reference_end": 9000,
         "query_start": 5000, "query_end": 9000, "strand": "-", "aligned_bp": 4000},
        {"reference": "ref", "query": "q2", "reference_start": 9000, "reference_end": 12000,
         "query_start": 0, "query_end": 3000, "strand": "+", "aligned_bp": 3000},
    ]
    summary = rearrangement_summary(blocks)
    assert summary["n_blocks"] == 3
    assert summary["n_forward_blocks"] == 2
    assert summary["n_reverse_blocks"] == 1
    assert summary["n_breakpoints"] == 2
    assert summary["n_translocations"] == 1
    assert summary["syntenic_fraction"] == pytest.approx(8000 / 12000)


def test_alignment_statistics_coverage_and_identity():
    records = [
        _record("ref", 0, 5000, "qry", 0, 5000, identity=1.0),
        _record("ref", 5000, 9000, "qry", 5000, 9000, identity=0.9),
    ]
    statistics = alignment_statistics(records, 10000, 20000, 1000, 0.0)
    assert statistics["n_alignments"] == 2
    assert statistics["aligned_bp"] == 9000
    assert statistics["query_coverage"] == pytest.approx(0.9)
    assert statistics["reference_coverage"] == pytest.approx(0.45)
    assert statistics["mean_identity"] == pytest.approx((5000 + 3600) / 9000)
    with pytest.raises(StepError):
        alignment_statistics(records, 10000, 20000, 100000, 0.0)


def test_write_fasta_round_trip(tmp_path):
    path = tmp_path / "out.fasta"
    entries = write_fasta(_fasta("ACGTACGT", "chr1"), "sequence", "position", path, "test")
    assert entries == [("chr1", 8)]
    assert path.read_text() == ">chr1\nACGTACGT\n"


def test_alignment_stats_operator_with_stub(monkeypatch):
    records = [
        _record("ref", 0, 5000, "chr", 0, 5000, identity=1.0),
        _record("ref", 5000, 9000, "chr", 5000, 9000, identity=0.9),
    ]
    monkeypatch.setattr(stats_module, "run_minimap2", lambda *args, **kwargs: records)
    step = stats_module.GenomeAlignmentStatsStep()
    ctx = _Ctx({"output": "stats"})
    step.run(ctx, [_fasta("A" * 9000, "chr"), _fasta("A" * 9000, "ref")])
    form = ctx["stats"]
    assert form.data.shape == (9, 1)
    assert form.labels["statistic"]["n_alignments"] == 0
    assert form.info["aligned_bp"] == 9000
    assert step.export(ctx)["n_alignments"] == 2


def test_synteny_operator_with_stub(monkeypatch):
    records = [
        _record("ref", 0, 5000, "chr", 0, 5000),
        _record("ref", 5000, 10000, "chr", 5000, 10000),
    ]
    monkeypatch.setattr(synteny_module, "run_minimap2", lambda *args, **kwargs: records)
    step = synteny_module.GenomeSyntenyBlocksStep()
    ctx = _Ctx({"output": "blocks", "min_block": 1000})
    step.run(ctx, [_fasta("A" * 10000, "chr"), _fasta("A" * 10000, "ref")])
    form = ctx["blocks"]
    assert form.data.shape == (1, 8)
    assert form.data[0, 6] == 10000
    assert form.info["n_blocks"] == 1


def test_rearrangement_operator_with_stub(monkeypatch):
    records = [
        _record("ref", 0, 5000, "chr", 0, 5000, strand="+"),
        _record("ref", 5000, 10000, "chr", 10000, 5000, strand="-"),
    ]
    monkeypatch.setattr(rearrangement_module, "run_minimap2", lambda *args, **kwargs: records)
    step = rearrangement_module.GenomeRearrangementSummaryStep()
    ctx = _Ctx({"output": "summary"})
    step.run(ctx, [_fasta("A" * 10000, "chr"), _fasta("A" * 10000, "ref")])
    form = ctx["summary"]
    assert form.data.shape == (10, 1)
    assert form.info["n_reverse_blocks"] == 1


@pytest.mark.skipif(shutil.which("minimap2") is None, reason="minimap2 is not installed")
def test_minimap2_aligns_identical_small_genomes(tmp_path):
    query = tmp_path / "query.fasta"
    reference = tmp_path / "reference.fasta"
    import random
    generator = random.Random(7)
    sequence = "".join(generator.choice("ACGT") for _ in range(20000))
    query.write_text(f">q\n{sequence}\n")
    reference.write_text(f">r\n{sequence}\n")
    records = stats_module.run_minimap2(query, reference, "asm5", 1, 300)
    assert records
    assert max(record["identity"] for record in records) > 0.99
