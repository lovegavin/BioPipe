"""Tests for the CDR graft operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_cdr_graft import (
    AntibodyCdrGraftStep,
    _regions,
    graft_sequence,
)
from src.task.step.steps.antibody_cdr_kabat import kabat_regions

# ANARCI/Kabat reference VHHs (tests/test_extension124.py fixtures).
DONOR = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYA"
    "DSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDS"
    "WGQGTQVTVSSGRYPYDVPDYGSGRA"
)
ACCEPTOR = (
    "QVQLQESGGGLVQAGGSLRLSCAASGYISDAYYMGWYRQAPGKEREFVATITHGTNTYYAD"
    "SVKGRFTISRDNAKNTVYLQMNSLKPEDTAVYYCAVLETRSYSFRYWGQGTQVTVSSLE"
)


def _form(sequences: list[str]):
    return encode_sequences(sequences, "sequence", "position", "protein")


def test_graft_replaces_all_cdrs() -> None:
    grafted, metadata = graft_sequence(DONOR, ACCEPTOR)
    donor_regions = {
        name: (start, end, residues) for name, start, end, residues in kabat_regions(DONOR)
    }
    acceptor_regions = {
        name: (start, end, residues) for name, start, end, residues in kabat_regions(ACCEPTOR)
    }
    assert [row["region"] for row in metadata] == ["CDR1", "CDR2", "CDR3"]
    expected = ACCEPTOR
    for name in ("CDR3", "CDR2", "CDR1"):
        a_start, a_end, _ = acceptor_regions[name]
        _, _, donor_residues = donor_regions[name]
        expected = expected[: a_start - 1] + donor_residues + expected[a_end:]
    assert grafted == expected
    assert len(grafted) != len(ACCEPTOR)
    for row in metadata:
        assert row["donor_residues"] in grafted
        assert row["donor_length"] == len(row["donor_residues"])


def test_graft_single_region_keeps_other_frameworks() -> None:
    grafted, metadata = graft_sequence(DONOR, ACCEPTOR, ("CDR3",))
    assert len(metadata) == 1 and metadata[0]["region"] == "CDR3"
    acceptor_regions = _regions(ACCEPTOR, "acceptor")
    start, end, residues = acceptor_regions["CDR3"]
    assert grafted[: start - 1] == ACCEPTOR[: start - 1]
    assert grafted[start - 1 : start - 1 + len(_regions(DONOR, "donor")["CDR3"][2])] == _regions(
        DONOR, "donor"
    )["CDR3"][2]


def test_runner_round_trip(tmp_path) -> None:
    ctx = Context(str(tmp_path / "graft"), {"params": {}})
    ctx["vhh"] = _form([DONOR, ACCEPTOR])
    run(
        ctx,
        [
            {
                "name": "antibody_cdr_graft",
                "inputs": ["vhh"],
                "params": {"donor_index": 1, "acceptor_index": 2, "output": "grafts"},
            }
        ],
    )
    form = ctx["grafts"]
    assert form.dims == ["graft", "statistic"]
    assert form.data.shape == (1, 4)
    assert form.data[0, 0] == pytest.approx(len(ACCEPTOR))
    assert form.data[0, 3] == pytest.approx(3.0)
    assert form.info["grafted_sequence"].startswith("QVQLQESGG")
    assert form.info["grafted_sequence"] != ACCEPTOR
    exports = sorted((tmp_path / "graft").rglob("*antibody_cdr_graft*.json"))
    assert len(exports) == 1


def test_validation_errors(tmp_path) -> None:
    step = AntibodyCdrGraftStep()
    assert step.definition["inputs_arity"] == 1
    with pytest.raises(StepError, match="region must be one of"):
        graft_sequence(DONOR, ACCEPTOR, ("CDR9",))

    ctx = Context(str(tmp_path / "errors"), {"params": {}})
    ctx["vhh"] = _form([DONOR, ACCEPTOR])
    with pytest.raises(StepError, match="unknown regions"):
        run(
            ctx,
            [
                {
                    "name": "antibody_cdr_graft",
                    "inputs": ["vhh"],
                    "params": {"donor_index": 1, "acceptor_index": 2, "regions": "CDR9"},
                }
            ],
        )
    with pytest.raises(StepError, match="must not repeat"):
        run(
            ctx,
            [
                {
                    "name": "antibody_cdr_graft",
                    "inputs": ["vhh"],
                    "params": {"donor_index": 1, "acceptor_index": 2, "regions": "CDR1,CDR1"},
                }
            ],
        )
    with pytest.raises(StepError, match="is outside the 2 input sequences"):
        run(
            ctx,
            [
                {
                    "name": "antibody_cdr_graft",
                    "inputs": ["vhh"],
                    "params": {"donor_index": 3, "acceptor_index": 2},
                }
            ],
        )
