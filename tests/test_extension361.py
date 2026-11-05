import sys
import types
from pathlib import Path

import numpy as np

from src.reader.readers.bgen_reader import BgenReader
from src.task.step.steps import structure_dssp_segments as dssp


class _FakeBgen:
    def __init__(self, probs):
        self._probs = probs
        self.ids = [f"v{i + 1}" for i in range(probs.shape[1])]
        self.samples = [f"s{i + 1}" for i in range(probs.shape[0])]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._probs


def _install_fake(monkeypatch, probs):
    module = types.SimpleNamespace(
        open_bgen=lambda path, verbose=False: _FakeBgen(probs)
    )
    monkeypatch.setitem(sys.modules, "bgen_reader", module)


def test_bgen_reader_decodes_four_plane_haplotype_dosage(monkeypatch):
    probs = np.array(
        [
            [[0.0, 1.0, 0.0, 1.0], [0.0, 1.0, 1.0, 0.0]],
            [[1.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 0.0]],
        ]
    )
    _install_fake(monkeypatch, probs)
    form = BgenReader().read(
        Path("example.bgen"), ["variant", "sample"],
        {"variant": "auto", "sample": "auto"},
    )
    expected = np.array([[2.0, 1.0], [1.0, np.nan]])
    np.testing.assert_allclose(form.data, expected, equal_nan=True)


def test_bgen_reader_keeps_three_plane_dosage(monkeypatch):
    probs = np.array(
        [
            [[0.0, 0.5, 0.5]],
            [[1.0, 0.0, 0.0]],
        ]
    )
    _install_fake(monkeypatch, probs)
    form = BgenReader().read(
        Path("example.bgen"), ["variant", "sample"],
        {"variant": "auto", "sample": "auto"},
    )
    np.testing.assert_allclose(form.data, np.array([[1.5, 0.0]]))


def test_dssp_retries_pdb_input_as_mmcif(tmp_path, monkeypatch):
    pdb = tmp_path / "input.pdb"
    pdb.write_text("ATOM      1  N   MET A   1      0.000   0.000   0.000\nEND\n")
    calls = []

    def fake_run(command, capture_output, text, timeout):
        calls.append(command)
        source = Path(command[3])
        output = Path(command[4])
        if source.suffix.lower() == ".pdb":
            return types.SimpleNamespace(
                returncode=1, stdout="",
                stderr="parse error at line 1: This file does not seem to be an mmCIF file",
            )
        output.write_text("  DSSP CONVERTED OUTPUT\n", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def fake_convert(source, target):
        Path(target).write_text("data_dummy\nloop_\n", encoding="utf-8")

    monkeypatch.setattr(dssp.subprocess, "run", fake_run)
    monkeypatch.setattr(dssp, "_pdb_to_mmcif", fake_convert)
    text = dssp.run_dssp("mkdssp", pdb, tmp_path)
    assert "DSSP CONVERTED OUTPUT" in text
    assert len(calls) == 2
    assert calls[0][3].endswith(".pdb")
    assert calls[1][3].endswith(".cif")
