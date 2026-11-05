"""GTF annotation operators must accept GTF role names (3.0.1 regression)."""

from __future__ import annotations

from pathlib import Path

from src.reader import read_source
from src.task.context import Context
from src.task.runner import run

GTF = """\
chr1\tsrc\tgene\t1\t100\t.\t+\t.\tgene_id "g1";
chr1\tsrc\texon\t1\t40\t.\t+\t.\tgene_id "g1"; transcript_id "t1";
chr1\tsrc\texon\t61\t100\t.\t+\t.\tgene_id "g1"; transcript_id "t1";
chr1\tsrc\tgene\t201\t300\t.\t-\t.\tgene_id "g2";
chr1\tsrc\texon\t201\t300\t.\t-\t.\tgene_id "g2"; transcript_id "t2";
"""


def test_gtf_annotation_ops_accept_gtf_columns(tmp_path: Path) -> None:
    path = tmp_path / "annot.gtf"
    path.write_text(GTF, encoding="utf-8")
    form = read_source(
        path,
        ["record", "field"],
        {"record": "auto", "field": "builtin"},
    )

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["annotation"] = form
    run(
        ctx,
        [
            {
                "name": "gff_feature_stats",
                "inputs": ["annotation"],
                "params": {"output": "stats"},
            },
            {
                "name": "gene_structure",
                "inputs": ["annotation"],
                "params": {"output": "structure"},
            },
            {
                "name": "annotation_gaps",
                "inputs": ["annotation"],
                "params": {"output": "gaps", "min_gap": 50},
            },
        ],
    )

    stats = ctx["stats"]
    count_column = stats.labels["statistic"]["count"]
    counts = {
        label: float(stats.data[index, count_column])
        for label, index in stats.labels["feature_type"].items()
    }
    assert counts["gene"] == 2
    assert counts["exon"] == 3

    structure = ctx["structure"]
    assert structure.data.shape[0] == 2
    n_exons = structure.data[:, structure.labels["statistic"]["n_exons"]]
    n_introns = structure.data[:, structure.labels["statistic"]["n_introns"]]
    assert sorted(n_exons.tolist()) == [1.0, 2.0]
    assert sorted(n_introns.tolist()) == [0.0, 1.0]

    gaps = ctx["gaps"]
    assert gaps.data.shape[0] == 1
    gap_length = gaps.data[0, gaps.labels["statistic"]["gap_length"]]
    assert float(gap_length) == 100.0
