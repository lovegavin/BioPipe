"""Tests for the Kabat CDR physicochemical profile operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_cdr_kabat import kabat_regions
from src.task.step.steps.antibody_cdr_physchem import (
    STATISTICS,
    AntibodyCdrPhyschemStep,
    cdr_physchem_row,
)
from src.task.step.steps.antibody_developability import _HYDROPHOBIC

VHH_1MEL = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYADSVKGRFTISQDNAK"
    "NTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSSGRYPYDVPDYGSGRA"
)


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(sequence=VHH_1MEL):
    return encode_sequences([sequence], "sequence", "position", "protein")


def _run(sequence=VHH_1MEL, **params):
    step = AntibodyCdrPhyschemStep()
    ctx = Ctx(params)
    step.run(ctx, [_form(sequence)])
    return ctx["out"], step.export(ctx)


def test_regions_and_labels():
    out, export = _run()
    order = sorted(out.labels["region"].items(), key=lambda item: item[1])
    assert [label for label, _ in order] == ["CDR1", "CDR2", "CDR3"]
    assert list(out.dims) == ["region", "statistic"]
    assert [label for label, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])] == list(
        STATISTICS
    )
    assert export["regions"] == ["CDR1", "CDR2", "CDR3"]
    assert out.info["region_sequences"] == {
        "CDR1": "PYCMG",
        "CDR2": "AINMGGGITYYADSVKG",
        "CDR3": "DSTIYASYYECGHGLSTGGYGYDS",
    }


def test_hand_computed_cdr_rows():
    cdr1, cdr2, cdr3 = (
        residues for region, _, _, residues in kabat_regions(VHH_1MEL) if region.startswith("CDR")
    )
    rows = {region: cdr_physchem_row(seq) for region, seq in (("CDR1", cdr1), ("CDR2", cdr2), ("CDR3", cdr3))}

    assert rows["CDR1"][0] == 5
    assert rows["CDR1"][6] == 0  # no NG/NS deamidation motif in PYCMG
    assert rows["CDR1"][7] == 1  # one cysteine
    assert rows["CDR3"][0] == 24
    assert rows["CDR3"][7] == 1  # one cysteine (ECGH)
    assert rows["CDR2"][4] == pytest.approx(
        sum(1 for amino in "AINMGGGITYYADSVKG" if amino in _HYDROPHOBIC) / 17
    )

    out, _ = _run()
    for row, region in enumerate(["CDR1", "CDR2", "CDR3"]):
        np.testing.assert_allclose(
            out.data[row], np.asarray(rows[region], np.float32), rtol=1e-5, atol=1e-5
        )


def test_standard_physchem_matches_biopython():
    Bio = pytest.importorskip("Bio.SeqUtils.ProtParam")
    out, _ = _run()
    sequence = out.info["region_sequences"]["CDR3"]
    analysis = Bio.ProteinAnalysis(sequence)
    row = cdr_physchem_row(sequence)
    assert row[1] == pytest.approx(analysis.molecular_weight(), rel=1e-4)
    # The operator keeps the pKa table of the protein_properties operator, which
    # differs from Biopython's table by up to ~0.7 pH units on very short loops.
    assert row[2] == pytest.approx(analysis.isoelectric_point(), abs=1.0)
    assert row[3] == pytest.approx(analysis.charge_at_pH(7.4), abs=0.5)


def test_single_region_selection():
    out, export = _run(regions="CDR3", ph=6.0)
    order = sorted(out.labels["region"].items(), key=lambda item: item[1])
    assert [label for label, _ in order] == ["CDR3"]
    assert export["regions"] == ["CDR3"]
    assert out.info["ph"] == 6.0


def test_empty_sequence_row_is_nan():
    row = cdr_physchem_row("")
    assert np.isnan(row).all()


def test_parameter_errors():
    with pytest.raises(StepError, match="regions"):
        _run(regions="CDR9")
    with pytest.raises(StepError, match="regions"):
        _run(regions="")
    with pytest.raises(StepError, match="ph"):
        _run(ph=15.0)


def test_multi_sequence_rejected():
    form = encode_sequences(["ACDEFGHIK", "ACDEFGHIK"], "sequence", "position", "protein")
    step = AntibodyCdrPhyschemStep()
    ctx = Ctx({})
    with pytest.raises(StepError, match="one sequence"):
        step.run(ctx, [form])


def test_short_sequence_rejected():
    with pytest.raises(StepError, match="too short"):
        _run("ACDE")
