import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_cdr_length_profile import (
    STATISTICS,
    AntibodyCdrLengthProfileStep,
    cdr_rows,
)

VHH_1MEL = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYADSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYY"
    "CAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS"
)
VHH_5VNV = (
    "QVQLQESGGGLVQAGGSLRLSCAASGYISDAYYMGWYRQAPGKEREFVATITHGTNTYYADSVKGRFTISRDNAKNTVYLQMNSLKPEDTAVYYC"
    "AVLETRSYSFRYWGQGTQVTVSSLE"
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(sequences):
    return encode_sequences(list(sequences), "sequence", "position", "protein")


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_1mel_hand_values():
    row = cdr_rows(VHH_1MEL)
    assert row["cdr1_length"] == 5
    assert row["cdr2_length"] == 17
    assert row["cdr3_length"] == 24
    assert row["total_cdr_length"] == 46
    assert np.isclose(row["cdr3_hydrophobic_fraction"], 8 / 24)
    assert row["cdr3_net_charge"] == -3
    assert row["_cdr"]["CDR1"] == "PYCMG"
    assert row["_cdr"]["CDR3"] == "DSTIYASYYECGHGLSTGGYGYDS"


def test_5vnv_hand_values():
    row = cdr_rows(VHH_5VNV)
    assert row["cdr1_length"] == 5
    assert row["cdr2_length"] == 16
    assert row["cdr3_length"] == 10
    assert row["total_cdr_length"] == 31
    assert row["cdr3_net_charge"] == 1
    assert np.isclose(row["cdr3_hydrophobic_fraction"], 4 / 10)


def test_step_matrix_and_info():
    form = _form([VHH_1MEL, VHH_5VNV])
    out, export = _run(AntibodyCdrLengthProfileStep(), {}, form)
    assert list(out.dims) == ["sequence", "statistic"]
    labels = [name for name, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])]
    assert labels == list(STATISTICS)
    assert out.data.shape == (2, 6)
    assert out.labels["sequence"] == {"seq1": 0, "seq2": 1}
    cdrs = list(STATISTICS)
    assert out.data[0, cdrs.index("cdr3_length")] == 24
    assert out.data[1, cdrs.index("cdr3_length")] == 10
    assert out.info["n_sequences"] == 2
    assert export["max_cdr3_length"] == 24


def test_runner_contract(tmp_path):
    form = _form([VHH_1MEL])
    work = tmp_path / "task"
    work.mkdir()
    ctx = Context(work, {"params": {}})
    ctx["seq"] = form
    run(ctx, [{"name": "antibody_cdr_length_profile", "inputs": ["seq"],
               "params": {"output": "profile"}}])
    out = ctx["profile"]
    assert out.data.shape == (1, 6)
    assert (ctx.out_dir / "steps" / "01_antibody_cdr_length_profile.json").is_file()


def test_errors():
    form = _form([VHH_1MEL])
    with pytest.raises(StepError, match="is required"):
        _run(AntibodyCdrLengthProfileStep(), {"position_dim": "other"}, form)
    with pytest.raises(StepError, match="regions must name"):
        _run(AntibodyCdrLengthProfileStep(), {"regions": ""}, form)
    with pytest.raises(StepError, match="regions must be CDR1"):
        _run(AntibodyCdrLengthProfileStep(), {"regions": "CDR9"}, form)
    with pytest.raises(StepError, match="too short|conserved"):
        _run(AntibodyCdrLengthProfileStep(), {}, _form(["ACDE"]))
