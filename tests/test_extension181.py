"""Tests for the ESM-IF binder-side interface redesign operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.step.steps._esm_if_common import chain_residues
from src.task.step.steps.esm_if_interface_redesign import EsmIfInterfaceRedesignStep
from src.task.step.steps.esm_if_redesign import _fixed_partial

CHECKPOINT = Path("/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt")


def _atom(serial, name, resname, chain, number, x, y, z, element):
    return (
        f"ATOM  {serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{0.0:>6.2f}"
        f"          {element:>2}"
    )


def complex_pdb(path: Path) -> Path:
    residues = ["ALA", "GLY", "SER", "THR", "VAL", "LEU"]
    lines = ["PARENT 1 TEST"]
    serial = 1
    for chain, z_offset, z_index in (("A", 0.0, 0), ("B", 6.0, 3)):
        for index, resname in enumerate(residues, start=1):
            z = z_offset if chain == "A" else (6.0 if index >= 3 else 30.0)
            for name, element, dy, dz in (
                ("N", "N", -1.0, 0.0),
                ("CA", "C", 0.0, 0.0),
                ("C", "C", 1.0, 0.0),
                ("O", "O", 1.6, 0.6),
            ):
                lines.append(
                    _atom(
                        serial,
                        name,
                        resname,
                        chain,
                        index,
                        3.8 * index,
                        dy,
                        z + dz,
                        element,
                    )
                )
                serial += 1
    path.write_text("\n".join(lines) + "\n")
    return path


def _form(path: Path):
    return read_source(
        path,
        ["atom", "field"],
        {"atom": "auto", "field": "builtin"},
        encoders={"chain": "labelencoder", "resname": "labelencoder"},
    )


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _params(path, **overrides):
    params = {
        "binder_chains": "A",
        "target_chains": "B",
        "cutoff": 8.0,
        "model_path": str(CHECKPOINT),
        "num_samples": 2,
        "temperature": 0.1,
        "seed": 1,
        "output": "designs",
    }
    params.update(overrides)
    return params


def _fake_loader(monkeypatch):
    class FakeModel:
        def sample(self, coords, partial_seq=None, temperature=1.0, confidence=None):
            return "".join("A" if piece == "<mask>" else piece for piece in partial_seq)

    class FakeTorch:
        @staticmethod
        def manual_seed(value):
            return None

    def loader(model_path, operator):
        return FakeModel(), object(), FakeTorch()

    def log_probs(model, alphabet, coords, sequence):
        return np.zeros(len(sequence), dtype=np.float64)

    monkeypatch.setattr(
        "src.task.step.steps.esm_if_interface_redesign.load_esm_if", loader
    )
    monkeypatch.setattr(
        "src.task.step.steps.esm_if_interface_redesign.residue_log_probs", log_probs
    )


def test_step_with_stub_model(tmp_path, monkeypatch):
    _fake_loader(monkeypatch)
    path = complex_pdb(tmp_path / "complex.pdb")
    form = _form(path)
    step = EsmIfInterfaceRedesignStep()
    ctx = Ctx(_params(path))
    step.run(ctx, [form])
    out = ctx["designs"]
    assert out.data.shape == (2, 3)
    assert list(out.dims) == ["sample", "statistic"]
    assert list(out.labels["statistic"]) == [
        "mean_log_prob",
        "interface_recovery",
        "n_designed",
    ]
    labels, names, coords = chain_residues(form, "field", "A")
    assert len(labels) == 6 and coords.shape == (6, 3, 3)
    interface = set(out.info["interface_positions"])
    assert interface == {2, 3, 4, 5, 6}
    native = out.info["native_sequence"]
    for sequence in out.info["sequences"]:
        for position in range(1, len(native) + 1):
            if position not in interface:
                assert sequence[position - 1] == native[position - 1]
        assert sequence[2] == "A"
    assert out.info["n_interface"] == 5
    export = step.export(ctx)
    assert export["n_samples"] == 2


def test_derived_target_and_cutoff(tmp_path, monkeypatch):
    _fake_loader(monkeypatch)
    path = complex_pdb(tmp_path / "complex.pdb")
    form = _form(path)
    step = EsmIfInterfaceRedesignStep()
    ctx = Ctx(_params(path, target_chains="", cutoff=6.5))
    step.run(ctx, [form])
    out = ctx["designs"]
    assert out.info["n_interface"] == 4
    assert out.info["cutoff"] == 6.5


def test_parameter_errors(tmp_path, monkeypatch):
    _fake_loader(monkeypatch)
    path = complex_pdb(tmp_path / "complex.pdb")
    form = _form(path)
    step = EsmIfInterfaceRedesignStep()
    with pytest.raises(StepError, match="cannot be both binder and target"):
        step.run(Ctx(_params(path, binder_chains="A,B", target_chains="B")), [form])
    with pytest.raises(StepError, match="cutoff must be in"):
        step.run(Ctx(_params(path, cutoff=0.0)), [form])
    with pytest.raises(StepError, match="temperature must be in"):
        step.run(Ctx(_params(path, temperature=5.0)), [form])
    with pytest.raises(StepError, match="num_samples must be between"):
        step.run(Ctx(_params(path, num_samples=0)), [form])
    with pytest.raises(StepError, match="seed must not be negative"):
        step.run(Ctx(_params(path, seed=-1)), [form])
    with pytest.raises(StepError, match="no binder residue is within"):
        step.run(Ctx(_params(path, cutoff=0.01)), [form])
    with pytest.raises(StepError, match="not found in the PDB form"):
        step.run(Ctx(_params(path, binder_chains="Z", target_chains="")), [form])


def test_dims_error(tmp_path, monkeypatch):
    _fake_loader(monkeypatch)
    path = complex_pdb(tmp_path / "complex.pdb")
    step = EsmIfInterfaceRedesignStep()
    with pytest.raises(StepError, match="a structure form with dims"):
        step.run(Ctx(_params(path)), [])


@pytest.mark.skipif(
    not CHECKPOINT.is_file(),
    reason="ESM-IF1 checkpoint is not available",
)
def test_official_interface_redesign(tmp_path):
    path = complex_pdb(tmp_path / "complex.pdb")
    form = _form(path)
    step = EsmIfInterfaceRedesignStep()
    ctx = Ctx(_params(path))
    step.run(ctx, [form])
    out = ctx["designs"]
    assert out.data.shape == (2, 3)
    native = out.info["native_sequence"]
    interface = set(out.info["interface_positions"])
    partial = _fixed_partial(native, [position - 1 for position in interface])
    assert partial.count("<mask>") == len(interface)
    for sequence in out.info["sequences"]:
        assert len(sequence) == len(native)
        for position in range(1, len(native) + 1):
            if position not in interface:
                assert sequence[position - 1] == native[position - 1]
