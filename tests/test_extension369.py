"""Tests for the annotation-derived genome operators (B7)."""

from __future__ import annotations

import numpy as np
import pytest
from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps._annotation_utils import (
    complement_intervals,
    parse_attributes,
)
from src.task.step.steps.genome_cds_check import GenomeCdsCheckStep
from src.task.step.steps.genome_gene_density import GenomeGeneDensityStep
from src.task.step.steps.genome_intergenic_regions import GenomeIntergenicRegionsStep
from src.task.step.steps.genome_promoter_extract import GenomePromoterExtractStep


FIELD_ORDER = (
    "seqid",
    "source",
    "type",
    "start",
    "end",
    "score",
    "strand",
    "phase",
    "attributes",
)
ENCODED = ("seqid", "source", "type", "strand", "attributes")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _gff(records):
    columns = {name: [] for name in FIELD_ORDER}
    for record in records:
        columns["seqid"].append(record["seqid"])
        columns["source"].append(record.get("source", "RefSeq"))
        columns["type"].append(record["type"])
        columns["start"].append(record["start"])
        columns["end"].append(record["end"])
        columns["score"].append(record.get("score", 0.0))
        columns["strand"].append(record.get("strand", "+"))
        columns["phase"].append(record.get("phase", 0))
        columns["attributes"].append(record.get("attributes", ""))
    encoders = {name: LabelEncoder() for name in ENCODED}
    codes = {
        name: encoders[name].fit_transform(columns[name]) for name in ENCODED
    }
    matrix = []
    for index in range(len(records)):
        matrix.append(
            [
                codes["seqid"][index],
                codes["source"][index],
                codes["type"][index],
                columns["start"][index],
                columns["end"][index],
                columns["score"][index],
                codes["strand"][index],
                columns["phase"][index],
                codes["attributes"][index],
            ]
        )
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["record", "field"],
        labels={
            "record": {f"r{index}": index for index in range(len(records))},
            "field": {name: index for index, name in enumerate(FIELD_ORDER)},
        },
        info={"encoders": {"field": encoders}},
    )


def _fasta(sequences, names=None):
    names = list(names or [f"seq{index}" for index in range(len(sequences))])
    width = max(len(sequence) for sequence in sequences)
    code_of = {"A": 0, "C": 1, "G": 2, "T": 3}
    data = np.full((len(sequences), width), 4, dtype=np.float32)
    for row, sequence in enumerate(sequences):
        codes = [code_of.get(base.upper(), 4) for base in sequence]
        data[row, : len(codes)] = codes
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {name: index for index, name in enumerate(names)},
            "position": {str(index): index for index in range(width)},
        },
        info={"sequences": [str(sequence) for sequence in sequences]},
    )


def _run(step, params, forms):
    ctx = Ctx(params)
    step.run(ctx, forms)
    return ctx["out"], step.export(ctx)


def test_parse_attributes_accepts_gff3_and_gtf() -> None:
    gff = parse_attributes("locus_tag=b0001;gene=thrL")
    gtf = parse_attributes('gene_id "g1"; transcript_id "t1";')
    assert gff["locus_tag"] == "b0001"
    assert gff["gene"] == "thrL"
    assert gtf["gene_id"] == "g1"
    assert gtf["transcript_id"] == "t1"


def test_complement_intervals_edges() -> None:
    assert complement_intervals([(10, 20)], 30) == [(1, 9), (21, 30)]
    assert complement_intervals([(1, 30)], 30) == []
    assert complement_intervals([(1, 5), (5, 10)], 12) == [(11, 12)]


def test_gene_density_counts_and_aligned_fraction() -> None:
    form = _gff(
        [
            {"seqid": "chr", "type": "gene", "start": 1, "end": 100},
            {"seqid": "chr", "type": "gene", "start": 201, "end": 300},
            {"seqid": "chr", "type": "gene", "start": 900, "end": 1000},
        ]
    )
    out, exported = _run(GenomeGeneDensityStep(), {"window": 500}, [form])
    assert out.dims == ["window", "statistic"]
    assert out.data.shape == (2, 6)
    assert list(out.labels["statistic"]) == [
        "window_start",
        "window_end",
        "n_features",
        "features_per_kb",
        "aligned_bp",
        "aligned_fraction",
    ]
    first = out.data[0]
    assert first[0] == 1 and first[1] == 500
    assert first[2] == 2
    assert first[4] == pytest.approx(200.0)
    assert first[5] == pytest.approx(0.4)
    second = out.data[1]
    assert second[0] == 501 and second[1] == 1000
    assert second[2] == 1
    assert second[4] == pytest.approx(101.0)
    assert second[5] == pytest.approx(0.202)
    assert exported["windows"] == 2


def test_gene_density_rejects_missing_feature_type() -> None:
    form = _gff([{"seqid": "chr", "type": "gene", "start": 1, "end": 100}])
    with pytest.raises(StepError, match="no 'rRNA' records"):
        _run(GenomeGeneDensityStep(), {"feature_type": "rRNA"}, [form])


def test_intergenic_regions_merge_overlapping_genes() -> None:
    form = _gff(
        [
            {"seqid": "chr", "type": "gene", "start": 1, "end": 100},
            {"seqid": "chr", "type": "gene", "start": 90, "end": 200},
            {"seqid": "chr", "type": "gene", "start": 301, "end": 400},
        ]
    )
    out, exported = _run(GenomeIntergenicRegionsStep(), {}, [form])
    assert out.data.shape == (1, 1)
    assert out.data[0, 0] == pytest.approx(100.0)
    assert list(out.labels["gap"]) == ["chr:201-300"]
    assert exported["total_gap_bp"] == 100


def test_intergenic_min_length_filters_short_gaps() -> None:
    form = _gff(
        [
            {"seqid": "chr", "type": "gene", "start": 1, "end": 100},
            {"seqid": "chr", "type": "gene", "start": 110, "end": 200},
        ]
    )
    out, _ = _run(GenomeIntergenicRegionsStep(), {"min_length": 20}, [form])
    assert out.data.shape[0] == 0


def test_promoter_plus_and_minus_windows() -> None:
    genome = "ACGT" * 15
    form = _gff(
        [
            {
                "seqid": "chr",
                "type": "gene",
                "start": 21,
                "end": 30,
                "strand": "+",
                "attributes": "locus_tag=plus",
            },
            {
                "seqid": "chr",
                "type": "gene",
                "start": 31,
                "end": 40,
                "strand": "-",
                "attributes": "locus_tag=minus",
            },
        ]
    )
    out, exported = _run(
        GenomePromoterExtractStep(),
        {"upstream": 5},
        [form, _fasta([genome], ["chr"])],
    )
    assert out.dims == ["promoter", "position"]
    assert out.data.shape[0] == 2
    assert len(out.info["sequences"]) == 2
    assert out.info["sequences"][0] == "TACGT"
    assert out.info["sequences"][1] == "TACGT"
    assert out.info["strand"] == ["+", "-"]
    assert exported["promoters"] == 2


def test_promoter_missing_sequence_raises() -> None:
    form = _gff([{"seqid": "missing", "type": "gene", "start": 2, "end": 4}])
    with pytest.raises(StepError, match="not in FASTA"):
        _run(
            GenomePromoterExtractStep(),
            {"upstream": 2},
            [form, _fasta(["ACGTACGT"], ["chr"])],
        )


def test_cds_check_reports_frame_start_stop() -> None:
    genome = "ATGAAATAA" + "A" * 21
    form = _gff(
        [
            {
                "seqid": "chr",
                "type": "CDS",
                "start": 1,
                "end": 9,
                "attributes": "locus_tag=good",
            }
        ]
    )
    out, exported = _run(
        GenomeCdsCheckStep(), {}, [form, _fasta([genome], ["chr"])]
    )
    row = out.data[0]
    assert list(out.labels["statistic"]) == [
        "length_ok",
        "start_ok",
        "stop_ok",
        "internal_stops",
        "protein_length",
    ]
    assert row[0] == 1 and row[1] == 1 and row[2] == 1
    assert row[3] == 0
    assert row[4] == 3
    assert exported["stop_ok"] == 1


def test_cds_check_counts_internal_stops() -> None:
    genome = "ATGTAATAA"
    form = _gff(
        [{"seqid": "chr", "type": "CDS", "start": 1, "end": 9, "strand": "+"}]
    )
    out, _ = _run(
        GenomeCdsCheckStep(), {}, [form, _fasta([genome], ["chr"])]
    )
    # ATG TAA TAA: in frame, valid start and stop, one internal stop.
    assert out.data[0, 0] == 1
    assert out.data[0, 1] == 1
    assert out.data[0, 2] == 1
    assert out.data[0, 3] == 1


def test_cds_check_out_of_range_raises() -> None:
    form = _gff([{"seqid": "chr", "type": "CDS", "start": 1, "end": 50}])
    with pytest.raises(StepError, match="outside sequence length"):
        _run(GenomeCdsCheckStep(), {}, [form, _fasta(["ACGT"], ["chr"])])
