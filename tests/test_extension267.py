from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context import Context
from src.task.runner import run


def _ctx(task_dir: Path, out_name: str, params: dict) -> Context:
    ctx = Context(str(task_dir / "task"), {"params": {}})
    ctx.step_params = {"output": out_name, **params}
    return ctx

from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_signal_peptide_v2 import (
    hydropathy,
    scan_signal_peptide,
    signal_rows,
    tat_motif,
    type_code,
)

OMPA = "MKKTAIAIAVALAGFATVAQA"
ALBUMIN = "MKWVTFISLLFLFSSAYSRGVFRR"
CHARGED = "MDEKRHDEKRHDEKRHDEKRHDEKRHDEKRHDEKRH"


def test_hydropathy_and_motifs():
    values = hydropathy("ALV")
    assert values[0] == pytest.approx(1.8)
    assert values[1] == pytest.approx(3.8)
    assert values[2] == pytest.approx(4.2)
    with pytest.raises(StepError, match="outside the Kyte-Doolittle scale"):
        hydropathy("AJA")
    assert tat_motif("MRRQLA")
    assert not tat_motif("MKKA")
    assert type_code(False, False) == 1
    assert type_code(True, False) == 2
    assert type_code(False, True) == 3
    assert type_code(True, True) == 4


def test_ompa_is_a_secretory_signal_peptide():
    row = scan_signal_peptide(OMPA)
    assert row["detected"] == 1
    assert row["type"] == "Sec/SPI"
    assert row["type_code"] == 1
    assert 1 <= row["cleavage_site"] < len(OMPA) - 1
    assert row["h_start"] >= 1
    assert row["h_end"] >= row["h_start"]


def test_albumin_prepro_is_detected():
    row = scan_signal_peptide(ALBUMIN)
    assert row["detected"] == 1
    assert row["h_mean"] >= 0.9


def test_charged_sequence_has_no_signal_peptide():
    row = scan_signal_peptide(CHARGED)
    assert row["detected"] == 0
    assert row["type"] == "none"
    assert row["cleavage_site"] == 0
    assert np.isnan(row["h_mean"])


def test_signal_rows_are_ordered():
    rows = signal_rows([OMPA, CHARGED])
    assert len(rows) == 2
    assert rows[0]["detected"] == 1
    assert rows[1]["detected"] == 0


def test_run_encodes_two_sequences(tmp_path):
    length = max(len(OMPA), len(CHARGED))
    sequences = [OMPA.ljust(length, "G"), CHARGED.ljust(length, "G")]
    form = encode_sequences(sequences, "sequence", "position", "protein")
    params = {"sequence_dim": "sequence", "position_dim": "position"}
    ctx = _ctx(tmp_path, "signals", params)
    ctx["seq"] = form
    run(ctx, [{"name": "sequence_signal_peptide_v2", "inputs": ["seq"], "params": params}])
    result = ctx["signals"]
    assert result.dims == ["peptide", "statistic"]
    assert result.data.shape == (2, 7)
    assert list(result.labels["peptide"]) == ["seq1", "seq2"]
    assert result.data[0, 0] == 1
    assert result.data[1, 0] == 0
    assert result.info["n_detected"] == 1
    assert result.info["types"][0] == "Sec/SPI"


def test_run_raises_when_nothing_is_detected(tmp_path):
    form = encode_sequences([CHARGED], "sequence", "position", "protein")
    params = {"sequence_dim": "sequence", "position_dim": "position"}
    ctx = _ctx(tmp_path, "signals", params)
    ctx["seq"] = form
    with pytest.raises(StepError, match="no sequence carries a detectable signal peptide"):
        run(ctx, [{"name": "sequence_signal_peptide_v2", "inputs": ["seq"], "params": params}])


def test_empty_sequence_is_rejected():
    with pytest.raises(StepError, match="empty sequence"):
        scan_signal_peptide("")
