"""Tests for the genome k-mer operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError

from src.task.step.steps._kmer_utils import canonical_kmers, mash_distance
from src.task.step.steps.genome_kmer_spectrum import GenomeKmerSpectrumStep
from src.task.step.steps.genome_kmer_similarity import GenomeKmerSimilarityStep
from src.task.step.steps.genome_mash_distance import GenomeMashDistanceStep

_CODE = {"A": 0, "C": 1, "G": 2, "T": 3, "N": 4}


def _fasta(sequences, names=None):
    names = names or [f"seq{i}" for i in range(len(sequences))]
    width = max(len(sequence) for sequence in sequences)
    data = np.full((len(sequences), width), 4, dtype=np.int16)
    for row, sequence in enumerate(sequences):
        for column, base in enumerate(sequence.upper()):
            data[row, column] = _CODE.get(base, 4)
    labels = {name: index for index, name in enumerate(names)}
    positions = {str(index): index for index in range(width)}
    form = Form(
        data=data,
        dims=["sequence", "position"],
        labels={"sequence": labels, "position": positions},
        info={"sequences": list(sequences), "alphabet_map": "ACGTN"},
    )
    form.validate()
    return form


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.task_dir = "."


def _run(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx, ctx["out"]


def test_canonical_kmers_hand_values():
    values = canonical_kmers("ACGTAC", 2)
    assert [int(value) for value in values] == [1, 6, 1, 12, 1]


def test_spectrum_hand_histogram():
    step = GenomeKmerSpectrumStep()
    ctx, out = _run(step, [_fasta(["ACGTACGT"])], {"k": 3})
    assert out.data.shape == (2, 2)
    assert out.labels["frequency"] == {"2": 0, "4": 1}
    assert np.allclose(out.data[:, 0], [1.0, 1.0])
    assert np.allclose(out.data[:, 1], [0.5, 0.5])
    assert out.info["distinct_kmers"] == 2
    assert out.info["singletons"] == 0
    assert ctx["out"] is out


def test_spectrum_rejects_short_k():
    step = GenomeKmerSpectrumStep()
    with pytest.raises(StepError, match="between 3 and 31"):
        _run(step, [_fasta(["ACGTACGT"])], {"k": 2})


def test_spectrum_requires_info_sequences():
    step = GenomeKmerSpectrumStep()
    form = _fasta(["ACGTACGT"])
    form.info.pop("sequences")
    with pytest.raises(StepError, match="lacks info.sequences"):
        _run(step, [form], {"k": 3})


def test_similarity_identical_genomes():
    step = GenomeKmerSimilarityStep()
    genome = _fasta(["ACGT" * 8])
    _, out = _run(step, [genome, genome], {"k": 3})
    values = {label: out.data[index, 0] for label, index in out.labels["statistic"].items()}
    assert values["jaccard"] == 1.0
    assert values["fraction_a_in_b"] == 1.0
    assert values["union"] == values["n_kmers_a"]


def test_similarity_partial_overlap():
    step = GenomeKmerSimilarityStep()
    first = _fasta(["ACGTACGT"])
    second = _fasta(["ACGTAAAA"])
    _, out = _run(step, [first, second], {"k": 3})
    values = {label: out.data[index, 0] for label, index in out.labels["statistic"].items()}
    assert 0.0 < values["jaccard"] < 1.0
    assert values["intersection"] <= min(values["n_kmers_a"], values["n_kmers_b"])


def test_mash_distance_zero_for_identical():
    step = GenomeMashDistanceStep()
    genome = _fasta(["ACGT" * 8])
    _, out = _run(step, [genome, genome], {"k": 3})
    values = {label: out.data[index, 0] for label, index in out.labels["statistic"].items()}
    assert values["distance"] == 0.0
    assert values["ani"] == 1.0


def test_mash_distance_formula():
    distance = mash_distance(0.5, 21)
    assert distance == pytest.approx(0.4054651081081644 / 21.0, rel=1e-12)
    assert mash_distance(0.0, 21) == float("inf")


def test_similarity_rejects_bad_k():
    step = GenomeKmerSimilarityStep()
    genome = _fasta(["ACGT" * 8])
    with pytest.raises(StepError, match="between 3 and 31"):
        _run(step, [genome, genome], {"k": 40})
