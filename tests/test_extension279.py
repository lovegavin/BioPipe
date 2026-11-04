"""esm_embedding_autoencoder: reconstruction errors."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from src.core.forms import Form
from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_autoencoder import reconstruction_errors


def _form(rows, labels=None):
    labels = labels or {f"s{i}": i for i in range(len(rows))}
    return Form(
        data=np.asarray(rows, dtype=np.float32),
        dims=["sequence", "embedding"],
        labels={"sequence": labels, "embedding": {f"f{i}": i for i in range(len(rows[0]))}},
        info={"missing_code": np.nan},
    )


def test_reconstruction_errors_deterministic():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(8, 4))
    first, loss = reconstruction_errors(data, hidden=6, latent=2, epochs=40, random_state=1)
    second, _ = reconstruction_errors(data, hidden=6, latent=2, epochs=40, random_state=1)
    assert first.shape == (8,)
    assert np.all(first >= 0)
    assert np.allclose(first, second)
    assert loss >= 0


def test_run_writes_error_table():
    import tempfile

    form = _form(np.arange(12, dtype=float).reshape(3, 4))
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["embeddings"] = form
    run(ctx, [{"name": "esm_embedding_autoencoder", "inputs": ["embeddings"], "params": {"output": "errors", "epochs": 5, "hidden": 4, "latent": 1}}])
    result = ctx["errors"]
    assert result.dims == ["sample", "statistic"]
    assert result.data.shape == (3, 1)
    assert result.info["n_samples"] == 3


def test_errors():
    with pytest.raises(StepError, match="latent must be at least 1"):
        reconstruction_errors(np.ones((2, 2)), latent=0)
    with pytest.raises(StepError, match="non-finite"):
        reconstruction_errors(np.array([[np.nan, 1.0]]))
