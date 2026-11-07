import numpy as np
import pytest
from operon_sdk import FileArtifact, Form, StepError

from src.task.step.steps.peptide_fragment_ions import PeptideFragmentIonsStep
from src.task.step.steps.peptide_isotope_envelope import PeptideIsotopeEnvelopeStep
from src.task.step.steps.peptide_modified_mass import PeptideModifiedMassStep


class Ctx(dict):
    def __init__(self, inputs, params):
        super().__init__()
        self.inputs = inputs
        self.step_params = params
        self.artifacts = {}

    def artifact_path(self, name):
        from pathlib import Path
        import tempfile

        root = Path(tempfile.mkdtemp(prefix="b30_"))
        target = root / name
        target.mkdir(parents=True, exist_ok=True)
        self.artifacts[name] = target
        return target


def peptides_form(sequences):
    names = [f"P{index}" for index in range(len(sequences))]
    data = np.zeros((len(sequences), 2), dtype="float64")
    data[:, 0] = np.arange(1, len(sequences) + 1)
    return Form(
        data,
        dims=["peptide", "field"],
        labels={
            "peptide": {name: position for position, name in enumerate(names)},
            "field": {"start": 0, "end": 1},
        },
        info={"sequences": list(sequences)},
    )


def run_step(step, inputs, params):
    ctx = Ctx(inputs, params)
    step.name = step.definition["id"]
    step.run(ctx, list(inputs.values()))
    return ctx


def test_fragment_ions_reference_values():
    step = PeptideFragmentIonsStep()
    ctx = run_step(
        step,
        {"peptides": peptides_form(["PEPTIDE"])},
        {"output": "fragments", "ion_types": "b,y", "max_charge": 1},
    )
    out = ctx["fragments"]
    labels = list(out.labels["fragment"])
    assert len(labels) == 12
    values = {label: row[5] for label, row in zip(labels, out.data)}
    assert values["P0:b1+"] == pytest.approx(98.06004031562, abs=1e-7)
    assert values["P0:b6+"] == pytest.approx(653.31408272181, abs=1e-7)
    assert values["P0:y1+"] == pytest.approx(148.06043423844, abs=1e-7)
    assert values["P0:y6+"] == pytest.approx(703.31447664463, abs=1e-7)


def test_fragment_ions_charge_two_and_skip_short():
    step = PeptideFragmentIonsStep()
    ctx = run_step(
        step,
        {"peptides": peptides_form(["GK"])},
        {"output": "fragments", "ion_types": "b,y", "max_charge": 2},
    )
    out = ctx["fragments"]
    assert out.data.shape[0] == 4
    assert out.info["n_peptides"] == 1
    assert set(out.data[:, 2].tolist()) == {0.0, 1.0}


def test_fragment_ions_reject_bad_ion():
    step = PeptideFragmentIonsStep()
    with pytest.raises(StepError, match="ion_types"):
        run_step(
            step,
            {"peptides": peptides_form(["PEPTIDE"])},
            {"output": "fragments", "ion_types": "c,z"},
        )


def test_fragment_ions_require_sequences_info():
    step = PeptideFragmentIonsStep()
    form = peptides_form(["PEPTIDE"])
    form.info.pop("sequences")
    with pytest.raises(StepError, match="info.sequences"):
        run_step(step, {"peptides": form}, {"output": "fragments"})


def test_isotope_envelope_reference_values():
    step = PeptideIsotopeEnvelopeStep()
    ctx = run_step(
        step,
        {"peptides": peptides_form(["PEPTIDE"])},
        {"output": "envelope", "max_peaks": 4, "charge": 1},
    )
    out = ctx["envelope"]
    assert out.data.shape == (1, 12)
    first_mass = out.data[0, 0]
    assert first_mass == pytest.approx(800.367, abs=0.01)
    mz_values = out.data[0, 0::3]
    assert np.all(np.diff(mz_values) > 0)
    fractions = out.data[0, 1::3]
    assert 0.0 < fractions[0] <= 1.0
    intensities = out.data[0, 2::3]
    assert intensities[0] == pytest.approx(100.0)


def test_isotope_envelope_charge_two_shifts_spacing():
    step = PeptideIsotopeEnvelopeStep()
    ctx = run_step(
        step,
        {"peptides": peptides_form(["PEPTIDE"])},
        {"output": "envelope", "max_peaks": 3, "charge": 2},
    )
    out = ctx["envelope"]
    spacing_one = out.data[0, 3] - out.data[0, 0]
    assert spacing_one == pytest.approx(0.5017, abs=0.001)


def test_modified_mass_carbamidomethyl():
    step = PeptideModifiedMassStep()
    ctx = run_step(
        step,
        {"peptides": peptides_form(["PEPC", "PEPTIDE"])},
        {"output": "modified", "fixed_mods": "C:57.02146372"},
    )
    out = ctx["modified"]
    labels = out.labels["peptide"]
    index = labels["P0"]
    assert out.data[index, 2] == pytest.approx(57.02146372, abs=1e-7)
    assert out.data[index, 1] - out.data[index, 0] == pytest.approx(57.02146372, abs=1e-7)
    index = labels["P1"]
    assert out.data[index, 2] == 0.0
    assert out.info["n_modified"] == 1


def test_modified_mass_rejects_bad_mods():
    step = PeptideModifiedMassStep()
    with pytest.raises(StepError, match="modification mass"):
        run_step(
            step,
            {"peptides": peptides_form(["PEPC"])},
            {"output": "modified", "fixed_mods": "C:abc"},
        )
