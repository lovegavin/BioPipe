"""esm_embedding_knn_density: kNN density scores."""

import numpy as np
import pytest

pytest.importorskip("sklearn")

from src.core.errors import StepError
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_knn_density import density_scores


def _data():
    rng = np.random.default_rng(4)
    normal = rng.normal(0.0, 0.05, size=(10, 3))
    return np.vstack([normal, [[8.0, 8.0, 8.0]]])


def test_matches_sklearn_neighbours():
    from sklearn.neighbors import NearestNeighbors

    data = _data()
    scores, flags = density_scores(data, k=3)
    distances, _ = NearestNeighbors(n_neighbors=4).fit(data).kneighbors(data)
    expected = distances[:, 1:].mean(axis=1)
    assert np.allclose(scores, expected)
    assert flags[-1] == 1
    assert flags[-1] == 1


def test_run_writes_rows():
    data = _data()
    form = Form(data=data.astype(np.float32), dims=["sequence", "embedding"], labels={"sequence": {f"s{i}": i for i in range(len(data))}, "embedding": {f"f{i}": i for i in range(3)}}, info={"missing_code": np.nan})
    ctx = Context("/tmp/bp289", {"params": {}})
    ctx["embeddings"] = form
    run(ctx, [{"name": "esm_embedding_knn_density", "inputs": ["embeddings"], "params": {"output": "density", "k": 3}}])
    result = ctx["density"]
    assert result.data.shape == (len(data), 2)
    assert result.info["n_outliers"] >= 1


def test_errors():
    with pytest.raises(StepError, match="at least 6 samples"):
        density_scores(np.ones((5, 2)), k=5)
    with pytest.raises(StepError, match="non-finite"):
        density_scores(np.array([[np.nan, 1.0], [1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 5.0], [5.0, 6.0]]), k=1)
