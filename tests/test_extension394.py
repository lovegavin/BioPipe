import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError

from src.task.step.steps._codon_bias_utils import clean_cds, enc_wright, gc3s_variants, rscu
from src.task.step.steps.codon_adaptation import CodonAdaptationStep, cai_value, reference_weights
from src.task.step.steps.codon_usage_bias import CodonUsageBiasStep
from src.task.step.steps.rscu_table import RscuTableStep


class Ctx:
    def __init__(self, params):
        self.step_params = dict(params)
        self.outputs = {}

    def __setitem__(self, key, value):
        self.outputs[key] = value

    def artifact_path(self, name):
        import tempfile, pathlib
        return pathlib.Path(tempfile.mkdtemp()) / name


def fasta_form(sequences):
    width = max(len(sequence) for sequence in sequences) if sequences else 1
    data = np.zeros((len(sequences), width), dtype=np.uint8)
    return Form(
        data,
        dims=["sequence", "position"],
        labels={"sequence": {f"s{index}": index for index in range(len(sequences))}},
        info={"sequences": [str(sequence) for sequence in sequences]},
    )


def run_step(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, list(inputs.values()))
    return ctx.outputs[params.get("output", step.definition["id"])]


def test_clean_cds_strips_terminal_stops():
    assert clean_cds("atgGCTTAA", "t") == "ATGGCT"
    with pytest.raises(ValueError):
        clean_cds("ATGG", "t")


def test_enc_and_gc3s_hand_values():
    single = "GCTGCTGCTGCT"
    assert clean_cds(single, "t") == single
    # CodonW leaves ENC undefined when no amino acid of some degeneracy class is polymorphic.
    assert np.isnan(enc_wright(single))
    assert gc3s_variants(single)["multi"] == pytest.approx(0.0)
    mixed = "GCTGCCGCTGCC"
    assert np.isnan(enc_wright(mixed))
    assert gc3s_variants(mixed)["multi"] == pytest.approx(0.5)
    full = "TTT" * 4 + "TTC" + "ATT" * 2 + "ATC" * 2 + "GCT" * 3 + "GCC" * 2 + "CTG" * 3 + "TTG"
    assert enc_wright(full) == pytest.approx(38.5)
    assert gc3s_variants(full)["multi"] == pytest.approx(0.5)


def test_gc3s_excludes_single_codon_families():
    # ATG (M) and TGG (W) are single-codon families and must not enter GC3s.
    values = gc3s_variants("ATGTGGGCT")
    assert values["multi"] == pytest.approx(0.0)
    assert values["all"] == pytest.approx(2.0 / 3.0)


def test_usage_bias_operator_rows():
    full = "TTT" * 4 + "TTC" + "ATT" * 2 + "ATC" * 2 + "GCT" * 3 + "GCC" * 2 + "CTG" * 3 + "TTG"
    out = run_step(CodonUsageBiasStep(), {"cds": fasta_form(["GCTGCTGCTGCT", full])},
                   {"output": "bias"})
    assert out.dims == ["sequence", "statistic"]
    assert out.data.shape == (2, 3)
    assert np.isnan(out.data[0, 0])
    assert out.data[1, 0] == pytest.approx(38.5)
    assert out.data[1, 1] == pytest.approx(0.5)


def test_reference_weights_and_cai_uniform():
    weights, optimal = reference_weights(["GCTGCC"], "t")
    assert weights["GCT"] == pytest.approx(1.0)
    assert weights["GCC"] == pytest.approx(1.0)
    assert "GCT" in optimal
    value, used = cai_value("GCTGCC", weights, "t")
    assert value == pytest.approx(1.0)
    assert used == 2


def test_cai_floors_absent_codon():
    weights, _ = reference_weights(["GCTGCTGCTGCT"], "t")
    assert weights["GCT"] == pytest.approx(1.0)
    assert weights["GCC"] == pytest.approx(0.125)
    value, used = cai_value("GCCGCC", weights, "t")
    assert value == pytest.approx(0.125)
    assert used == 2


def test_adaptation_operator_matches_weights():
    out = run_step(
        CodonAdaptationStep(),
        {"cds": fasta_form(["GCTGCC"]), "reference": fasta_form(["GCTGCC"])},
        {"output": "adapt"},
    )
    assert out.data.shape == (1, 2)
    assert out.data[0, 0] == pytest.approx(1.0)
    assert out.data[0, 1] == pytest.approx(2.0)


def test_rscu_sums_to_family_size():
    out = run_step(RscuTableStep(), {"cds": fasta_form(["GCTGCCGCTGCC"])}, {"output": "rscu"})
    assert out.data.shape == (61, 3)
    labels = out.labels["codon"]
    ala = [labels[codon] for codon in ("GCT", "GCC", "GCA", "GCG")]
    total = sum(float(out.data[index, 2]) for index in ala)
    assert total == pytest.approx(4.0)
    assert out.data[labels["GCT"], 2] == pytest.approx(2.0)


def test_usage_bias_rejects_empty_input():
    with pytest.raises(StepError):
        run_step(CodonUsageBiasStep(), {"cds": fasta_form([])}, {"output": "bias"})
