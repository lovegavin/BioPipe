import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.task.step.steps._codon_design_utils import (
    design_metrics,
    forbidden_hits,
    gc_fraction,
    harmonize,
    optimize,
    translate,
)
from src.task.step.steps.codon_design_qc import CodonDesignQcStep
from src.task.step.steps.codon_gc_harmonize import CodonGcHarmonizeStep
from src.task.step.steps.codon_optimize import CodonOptimizeStep, read_reference_cds_from_sequences


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def fasta_form(names, sequences):
    data = np.zeros((len(sequences), 1), dtype=np.float64)
    return Form(
        data,
        dims=["sequence", "position"],
        labels={"sequence": {name: index for index, name in enumerate(names)}},
        info={"sequences": list(sequences), "alphabet_map": "ACGT"},
    )


def test_translate_and_metrics():
    dna = "ATGGCTGCTTAATAA"
    assert translate(dna).startswith("MAA")
    metrics = design_metrics("ATGGCTGCTTAA", {"ATG": 1.0, "GCT": 1.0, "GCC": 0.5}, ["GAATTC"])
    assert metrics["length_bp"] == 12
    assert metrics["n_codons"] == 4
    assert metrics["gc_fraction"] == pytest.approx(gc_fraction("ATGGCTGCTTAA"))
    assert metrics["forbidden_sites"] == 0
    assert metrics["ends_with_stop"] is True


def test_forbidden_hits_both_strands():
    assert forbidden_hits("AAAGAATTCAAA", ["GAATTC"]) == 1
    assert forbidden_hits("AAAGAATTCTTT", ["GAATTC"]) == 1
    assert forbidden_hits("AAA", ["GAATTC"]) == 0


def reference_weights():
    names = ["ref1", "ref2", "ref3", "ref4", "ref5"]
    alanine = "ATGAAA" + "GCT" * 8 + "TAA"
    alternative = "ATGAAA" + "GCC" * 8 + "TAA"
    sequences = [alanine, alanine, alanine, alternative, alternative]
    return names, sequences


def test_reference_weights_favour_frequent_codons():
    names, sequences = reference_weights()
    weights, used = read_reference_cds_from_sequences(sequences)
    assert used == 5
    assert weights["GCT"] == 1.0
    assert weights["GCC"] == pytest.approx(16 / 24)


def test_optimize_uses_reference_and_preserves_protein():
    _, sequences = reference_weights()
    weights, _ = read_reference_cds_from_sequences(sequences)
    dna = optimize("MK", weights, [], (0.0, 0.0), 10)
    assert translate(dna) == "MK"
    assert dna == "ATGAAA"


def test_optimize_avoids_motif_spanning_junction():
    weights = {"ATG": 1.0, "TTT": 1.0, "TTC": 0.5}
    dna = optimize("MF", weights, ["ATGTTT"], (0.0, 1.0), 10)
    assert translate(dna) == "MF"
    assert forbidden_hits(dna, ["ATGTTT"]) == 0


def test_harmonize_moves_gc_and_preserves_protein():
    weights = {
        "GCT": 0.2,
        "GCC": 1.0,
        "GGA": 1.0,
        "GGG": 0.2,
    }
    sequence = "GGAGCTGGAGCTGGAGCT"
    harmonised = harmonize(sequence, weights, 0.9, [], 10)
    assert translate(harmonised) == translate(sequence)
    assert gc_fraction(harmonised) > gc_fraction(sequence)


def test_optimize_operator_end_to_end():
    names, references = reference_weights()
    proteins = fasta_form(["p1"], ["MK"])
    cds = fasta_form(names, references)
    ctx = Ctx({"output": "dna", "motifs": "ATGTTT", "gc_min": 0.2, "gc_max": 0.8})
    CodonOptimizeStep().run(ctx, [proteins, cds])
    dna = ctx["dna"]
    designed = dna.info["sequences"][0]
    assert translate(designed) == "MK"
    assert designed.startswith("ATG")
    assert dna.dims == ["sequence", "position"]
    assert dna.info["sequences"] == [designed]
    assert dna.info["metrics"]["p1"]["cai"] > 0
    assert dna.info["metrics"]["p1"]["forbidden_sites"] == 0


def test_optimize_rejects_nonstandard_residue():
    names, references = reference_weights()
    proteins = fasta_form(["p1"], ["MX"])
    cds = fasta_form(names, references)
    ctx = Ctx({"output": "dna"})
    with pytest.raises(StepError):
        CodonOptimizeStep().run(ctx, [proteins, cds])


def test_harmonize_operator_and_qc():
    names, references = reference_weights()
    cds = fasta_form(["s1"], ["GGAGCTGGAGCTGGAGCT"])
    ref = fasta_form(names, references)
    ctx = Ctx({"output": "dna", "target_gc": 0.9})
    CodonGcHarmonizeStep().run(ctx, [cds, ref])
    harmonised = ctx["dna"].info["sequences"][0]
    assert translate(harmonised) == translate("GGAGCTGGAGCTGGAGCT")

    qc_ctx = Ctx({"output": "qc", "motifs": "GAATTC"})
    CodonDesignQcStep().run(qc_ctx, [fasta_form(["s1"], [harmonised]), ref])
    qc = qc_ctx["qc"]
    assert qc.data.shape == (1, 5)
    assert qc.data[0, 4] == len(harmonised)
