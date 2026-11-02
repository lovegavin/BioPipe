"""esm_embedding_pca_reconstruction: per-sample PCA error."""

import numpy as np
import pytest

pytest.importorskip("sklearn")

from src.core.errors import StepError
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_pca_reconstruction import reconstruction_errors


def _form(rows):
    return Form(
        data=np.asarray(rows, dtype=np.float32),
        dims=["sequence", "embedding"],
        labels={"sequence": {f"s{i}": i for i in range(len(rows))}, "embedding": {f"f{i}": i for i in range(len(rows[0]))}},
        info={"missing_code": np.nan},
    )


def test_matches_sklearn_pca():
    from sklearn.decomposition import PCA

    rng = np.random.default_rng(3)
    data = rng.normal(size=(10, 5))
    errors, mean = reconstruction_errors(data, n_components=2)
    pca = PCA(n_components=2).fit(data)
    rebuilt = pca.inverse_transform(pca.transform(data))
    expected = ((rebuilt - data) ** 2).mean(axis=1)
    assert np.allclose(sorted(errors), sorted(expected), atol=1e-9)
    assert mean == pytest.approx(expected.mean())


def test_run_writes_error_table():
    ctx = Context("/tmp/bp282", {"params": {}})
    ctx["embeddings"] = _form(np.arange(12, dtype=float).reshape(3, 4))
    run(ctx, [{"name": "esm_embedding_pca_reconstruction", "inputs": ["embeddings"], "params": {"output": "errors"}}])
    result = ctx["errors"]
    assert result.data.shape == (3, 1)
    assert result.info["n_components"] == 2


def test_errors():
    with pytest.raises(StepError, match="at least two samples"):
        reconstruction_errors(np.ones((1, 3)))
    with pytest.raises(StepError, match="non-finite"):
        reconstruction_errors(np.array([[np.nan, 1.0], [2.0, 3.0]]))
