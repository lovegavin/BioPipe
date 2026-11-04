"""structure_disorder_profile: B-factor disorder proxies."""

import numpy as np
import pytest

from src.core.forms import Form
from src.core.errors import StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_disorder_profile import disorder_rows, residue_table


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}
        self.artifacts = {}


def _form(rows):
    columns = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element", "bfactor")
    encoders = {}
    data = []
    for row in rows:
        values = []
        for name, value in zip(columns, row):
            if name in ("x", "y", "z", "residue_number", "bfactor"):
                values.append(float(value))
            else:
                if name not in encoders:
                    encoders[name] = LabelEncoder()
                    encoders[name].fit_transform([str(value)])
                encoders[name].fit_transform([str(value)])
                values.append(float(encoders[name].fit_transform([str(value)])[0]))
        data.append(values)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {f"atom{i}": i for i in range(len(rows))}, "field": {name: i for i, name in enumerate(columns)}},
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _rows(bfactors, numbers=(1, 2, 4)):
    return [
        (float(n), 0.0, 0.0, n, "ALA", "A", "CA", "C", b)
        for n, b in zip(numbers, bfactors)
    ]


def test_disorder_rows_z_scores_and_gaps():
    form = _form(_rows((10.0, 20.0, 30.0)))
    rows = disorder_rows(residue_table(form, "atom", "field"))
    assert [round(row["bfactor_z"], 6) for row in rows] == [round(-1.224745, 6), 0.0, round(1.224745, 6)]
    assert [row["gap_to_next"] for row in rows] == [0, 1, 0]
    assert round(rows[0]["disorder_score"], 6) == -0.612372
    assert round(rows[1]["disorder_score"], 6) == 0.5
    assert round(rows[2]["disorder_score"], 6) == 0.612372


def test_disorder_rows_clips_z_scores():
    form = _form(_rows((10.0, 20.0, 100.0)))
    rows = disorder_rows(residue_table(form, "atom", "field"), z_clip=1.0)
    assert max(row["bfactor_z"] for row in rows) == 1.0


def test_validation_errors():
    with pytest.raises(StepError, match="carries no 'bfactor' column"):
        residue_table(Form(data=np.zeros((1, 2)), dims=["atom", "field"], labels={"atom": {"a": 0}, "field": {"x": 0, "y": 1}}, info={}), "atom", "field")


def test_run_writes_profile():
    form = _form(_rows((10.0, 20.0, 30.0)))
    import tempfile
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_disorder_profile", "inputs": ["pdb"], "params": {"output": "disorder", "atom_dim": "atom", "field_dim": "field"}}])
    result = ctx["disorder"]
    assert result.dims == ["residue", "statistic"]
    assert result.data.shape == (3, 4)
    assert result.info["mean_disorder"] == pytest.approx(0.16667, rel=1e-3)
    assert result.info["missing_residues"] == 1
