"""Antibody developability panel (v1.21.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_developability import (
    AntibodyDevelopabilityStep,
    count_motif,
    count_sequons,
    developability_row,
    longest_run,
)

VHH = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVS"
NAMES = [
    "length",
    "molecular_weight",
    "isoelectric_point",
    "net_charge_ph6",
    "net_charge_ph7",
    "n_cysteines",
    "n_deamidation",
    "n_isomerization",
    "n_glycosylation",
    "longest_hydrophobic_run",
    "hydrophobic_fraction",
    "charge_asymmetry",
]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(sequences):
    return encode_sequences(
        sequences,
        "sequence",
        "position",
        "protein",
        labels={
            "sequence": {
                "seq%d" % (index + 1): index for index in range(len(sequences))
            },
            "position": {
                str(index): index
                for index in range(max((len(s) for s in sequences), default=1))
            },
        },
        info_extra={"missing_code": np.nan},
    )


def _run(sequences, params=None):
    step = AntibodyDevelopabilityStep()
    ctx = Ctx(params or {})
    step.run(ctx, [_form(sequences)])
    return ctx["out"], step.export(ctx)


def test_statistics_are_the_documented_panel():
    form, _ = _run([VHH])
    assert form.dims == ["sequence", "statistic"]
    assert list(form.labels["statistic"]) == NAMES


def test_matches_biopython_oracle():
    bio = pytest.importorskip("Bio.SeqUtils.ProtParam")
    form, export = _run([VHH])
    analysis = bio.ProteinAnalysis(VHH)
    row = dict(zip(form.labels["statistic"], form.data[0].tolist()))

    assert row["length"] == len(VHH)
    assert row["molecular_weight"] == pytest.approx(
        analysis.molecular_weight(), rel=1e-4
    )
    assert row["isoelectric_point"] == pytest.approx(
        analysis.isoelectric_point(), abs=0.25
    )
    assert row["net_charge_ph7"] == pytest.approx(
        analysis.charge_at_pH(7.4), abs=0.6
    )
    assert row["net_charge_ph6"] > row["net_charge_ph7"]
    assert export["n_sequences"] == 1
    assert export["mean_isoelectric_point"] == pytest.approx(
        row["isoelectric_point"], rel=1e-5
    )


def test_hand_computed_motifs_and_runs():
    assert count_motif("NGNGDPCC", "NG") == 2
    assert count_motif("AAAA", "AA") == 3  # overlapping occurrences
    assert count_sequons("NSTNPSNAT") == 2  # NPS is blocked by proline
    assert longest_run("AVVVVLMK", set("AVILMFWY")) == 7

    # NGNGDPCC: two NG deamidation motifs, one DP, two cysteines, no sequon.
    values = dict(zip(NAMES, developability_row("NGNGDPCC")))
    assert values["length"] == 8
    assert values["n_deamidation"] == 2
    assert values["n_isomerization"] == 1
    assert values["n_cysteines"] == 2
    assert values["n_glycosylation"] == 0
    assert values["longest_hydrophobic_run"] == 0
    assert values["hydrophobic_fraction"] == 0.0


def test_multiple_sequences_and_custom_ph():
    form, _ = _run([VHH, "GGGG"], {"low_ph": 5.5, "high_ph": 7.0})
    assert list(form.labels["sequence"]) == ["seq1", "seq2"]
    assert form.data[1, 0] == 4
    assert form.info["low_ph"] == pytest.approx(5.5)
    assert form.info["high_ph"] == pytest.approx(7.0)


def test_empty_sequence_row_is_nan():
    form, _ = _run([VHH, ""])
    assert np.all(np.isnan(form.data[1]))


def test_errors():
    step = AntibodyDevelopabilityStep()
    with pytest.raises(StepError, match="expected"):
        step.run(Ctx({"sequence_dim": "peptide"}), [_form([VHH])])
