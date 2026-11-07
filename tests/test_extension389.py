"""Numerical and contract tests for the protein QC operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import get_encoder
from src.task.step.steps._protein_qc_utils import (
    AA20,
    clean_sequence,
    composition,
    extinction_coefficients,
    instability_index,
)
from src.task.step.steps.protein_composition import ProteinCompositionStep
from src.task.step.steps.protein_extinction import ProteinExtinctionStep
from src.task.step.steps.protein_instability import ProteinInstabilityStep


class Ctx:
    def __init__(self, **params):
        self.step_params = params
        self.outputs = {}

    def __setitem__(self, key, value):
        self.outputs[key] = value

    def __getitem__(self, key):
        return self.outputs[key]


def _protein_form(sequences, names=None):
    names = names or [f"p{i + 1}" for i in range(len(sequences))]
    width = max(len(s) for s in sequences)
    alphabet = sorted(set("".join(sequences)) | {"A"})
    mapping = {aa: i for i, aa in enumerate(alphabet)}
    unknown = len(alphabet)
    data = np.full((len(sequences), width), float(unknown), dtype=np.float32)
    for row, seq in enumerate(sequences):
        for col, aa in enumerate(seq):
            data[row, col] = mapping.get(aa, unknown)
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={"sequence": {n: i for i, n in enumerate(names)},
                "position": {str(i): i for i in range(width)}},
        info={"representation": "sequence_codes", "alphabet": "protein",
              "alphabet_map": mapping, "unknown_code": unknown, "missing_code": np.nan},
    )


def test_composition_counts():
    counts = composition("MRW")
    assert counts[AA20.index("M")] == 1
    assert counts[AA20.index("R")] == 1
    assert counts[AA20.index("W")] == 1
    assert sum(counts) == 3


def test_composition_rejects_nonstandard():
    with pytest.raises(StepError, match="unsupported residue"):
        clean_sequence("MX", "test")


def test_extinction_values():
    reduced, cystine, a280 = extinction_coefficients("MRW")
    assert reduced == 5500
    assert cystine == 5500
    assert a280 == pytest.approx(5500 / 491.6069, rel=1e-9)
    reduced, cystine, _ = extinction_coefficients("WYCC")
    assert reduced == 6990
    assert cystine == 7115


def test_instability_reference_value():
    value = instability_index("MKWVTFISLLFLFSSAYSRGVFRR")
    assert value == pytest.approx(44.02916666666667, rel=1e-6)
    assert instability_index("AAAA") == pytest.approx(7.5)


def test_composition_operator():
    form = _protein_form(["MRW", "AAA"], ["a", "b"])
    ctx = Ctx(output="composition")
    ProteinCompositionStep().run(ctx, [form])
    out = ctx["composition"]
    assert out.dims == ["sequence", "residue"]
    assert out.data.shape == (2, 20)
    assert out.data[0].sum() == 3
    assert out.data[0, AA20.index("W")] == 1


def test_extinction_operator():
    form = _protein_form(["WYCC"])
    ctx = Ctx(output="extinction")
    ProteinExtinctionStep().run(ctx, [form])
    out = ctx["extinction"]
    assert list(out.labels["statistic"]) == ["molar_reduced", "molar_cystine", "a280_1mg_ml"]
    assert out.data[0, 0] == 6990
    assert out.data[0, 1] == 7115


def test_instability_operator_cutoff():
    form = _protein_form(["AAAA", "MKWVTFISLLFLFSSAYSRGVFRR"])
    ctx = Ctx(stable_cutoff=40.0, output="instability")
    ProteinInstabilityStep().run(ctx, [form])
    out = ctx["instability"]
    assert out.data[0, 1] == 1.0
    assert out.data[1, 1] == 0.0
    assert out.data[1, 0] == pytest.approx(44.02916666666667, rel=1e-6)


def test_operator_rejects_bad_residue():
    form = _protein_form(["MX"])
    ctx = Ctx()
    with pytest.raises(StepError, match="no protein sequences with standard residues"):
        ProteinCompositionStep().run(ctx, [form])


def test_composition_skips_nonstandard_from_raw_sequences():
    form = _protein_form(["MKWVTFISLL", "MKU"])
    form.info["sequences"] = ["MKWVTFISLL", "MKU"]
    ctx = Ctx(output="composition")
    step = ProteinCompositionStep()
    step.run(ctx, [form])
    out = ctx["composition"]
    assert out.data.shape[0] == 1
    assert out.labels["sequence"] == {"p1": 0}
    assert step.export(ctx)["skipped_unsupported"] == 1
