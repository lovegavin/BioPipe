"""Tests for antibody_cdr_kabat, checked against ANARCI Kabat output."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_cdr_kabat import (
    REGIONS,
    AntibodyCdrKabatStep,
    kabat_regions,
)

# Sequences and their ANARCI/Kabat CDRs (abnumber 0.4.4 + hmmscan 3.4 on the
# RCSB entity sequences of the deposited VHH structures).
FIXTURES = {
    "1MEL": (
        "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYA"
        "DSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDS"
        "WGQGTQVTVSSGRYPYDVPDYGSGRA",
        "PYCMG",
        "AINMGGGITYYADSVKG",
        "DSTIYASYYECGHGLSTGGYGYDS",
    ),
    "5VNV": (
        "QVQLQESGGGLVQAGGSLRLSCAASGYISDAYYMGWYRQAPGKEREFVATITHGTNTYYAD"
        "SVKGRFTISRDNAKNTVYLQMNSLKPEDTAVYYCAVLETRSYSFRYWGQGTQVTVSSLE",
        "AYYMG",
        "TITHGTNTYYADSVKG",
        "LETRSYSFRY",
    ),
    "3EAK": (
        "QVQLVESGGGLVQPGGSLRLSCAASGGSEYSYSTFSLGWFRQAPGQGLEAVAAIASMGGLT"
        "YYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAAVRGYFMRLPSSHNFRYWGQGT"
        "LVTVSSRGRHHHHHH",
        "SYSTFSLG",
        "AIASMGGLTYYADSVKG",
        "VRGYFMRLPSSHNFRY",
    ),
    "5IMK": (
        "QVQLVESGGGLVQAGGSLRLSCAASGRTFSSYGMGWFRQAPGKEREFVAAIRWNGGSTYYA"
        "DSVKGRFTISRDNAKNTVYLQMNSLKPEDTAVYYCAAGRWDKYGSSFQDEYDYWGQGTQVT"
        "VSSHHHHHH",
        "SYGMG",
        "AIRWNGGSTYYADSVKG",
        "GRWDKYGSSFQDEYDY",
    ),
}


def _protein_form(sequences):
    return encode_sequences(
        sequences,
        "sequence",
        "position",
        "protein",
        labels={
            "sequence": {"s%d" % (index + 1): index for index in range(len(sequences))},
            "position": {
                str(index): index
                for index in range(max((len(s) for s in sequences), default=1))
            },
        },
        info_extra={"missing_code": np.nan},
    )


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


@pytest.mark.parametrize("pdb_id", sorted(FIXTURES))
def test_cdr_sequences_match_anarci_kabat(pdb_id):
    sequence, cdr1, cdr2, cdr3 = FIXTURES[pdb_id]
    regions = dict((region, residues) for region, _start, _end, residues in kabat_regions(sequence))
    assert regions["CDR1"] == cdr1
    assert regions["CDR2"] == cdr2
    assert regions["CDR3"] == cdr3


def test_regions_tile_the_domain():
    sequence, _cdr1, _cdr2, _cdr3 = FIXTURES["1MEL"]
    rows = kabat_regions(sequence)
    assert [row[0] for row in rows] == list(REGIONS)
    assert rows[0][1] == 1
    for previous, current in zip(rows, rows[1:]):
        assert current[1] == previous[2] + 1, (previous, current)
    assert "".join(row[3] for row in rows) == sequence[: rows[-1][2]]
    assert rows[-1][2] == 133  # the C-terminal tag is not part of framework 4
    assert rows[-1][2] < len(sequence)


def test_step_writes_region_statistic():
    sequence, cdr1, cdr2, cdr3 = FIXTURES["3EAK"]
    step = AntibodyCdrKabatStep()
    ctx = Ctx({})
    step.run(ctx, [_protein_form([sequence])])
    form = ctx["out"]
    assert form.dims == ["region", "statistic"]
    assert list(form.labels["region"]) == list(REGIONS)
    assert list(form.labels["statistic"]) == ["start", "end", "length"]
    starts = form.data[:, form.labels["statistic"]["start"]]
    ends = form.data[:, form.labels["statistic"]["end"]]
    lengths = form.data[:, form.labels["statistic"]["length"]]
    np.testing.assert_allclose(lengths, ends - starts + 1)
    assert form.info["cdr_sequences"] == {"CDR1": cdr1, "CDR2": cdr2, "CDR3": cdr3}
    assert form.info["numbering_scheme"] == "kabat"
    export = step.export(ctx)
    assert [row["region"] for row in export["regions"]] == list(REGIONS)
    assert export["cdr_sequences"]["CDR2"] == cdr2


def test_step_can_hide_frameworks():
    sequence = FIXTURES["5IMK"][0]
    step = AntibodyCdrKabatStep()
    ctx = Ctx({"include_frameworks": False})
    step.run(ctx, [_protein_form([sequence])])
    form = ctx["out"]
    assert list(form.labels["region"]) == ["CDR1", "CDR2", "CDR3"]


def test_step_errors():
    step = AntibodyCdrKabatStep()
    sequence = FIXTURES["5VNV"][0]
    with pytest.raises(StepError, match="exactly one VH/VHH sequence"):
        step.run(Ctx({}), [_protein_form([sequence, sequence])])
    with pytest.raises(StepError, match="too short"):
        kabat_regions("ACDE")
    with pytest.raises(StepError, match="must not be empty"):
        kabat_regions("")
    with pytest.raises(StepError, match="conserved 'LSC'"):
        kabat_regions("M" * 120)
    no_fr2 = sequence.replace("WYRQ", "AYRQ", 1)
    with pytest.raises(StepError, match="conserved 'W..RQ'"):
        kabat_regions(no_fr2)


def test_identity_gate_rejects_distant_sequences(monkeypatch):
    import src.task.step.steps.antibody_cdr_kabat as module

    sequence = FIXTURES["5VNV"][0]
    monkeypatch.setattr(module, "MIN_TEMPLATE_IDENTITY", 1.01)
    with pytest.raises(StepError, match="does not align"):
        module.kabat_regions(sequence)
