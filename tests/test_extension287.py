"""esm_embedding_isolation_forest: novelty scores."""

import numpy as np
import pytest

pytest.importorskip("sklearn")

from src.core.errors import StepError
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_isolation_forest import novelty_scores


def _data():
    rng = np.random.default_rng(0)
    normal = rng.normal(0.0, 0.05, size=(12, 3))
    return np.vstack([normal, [[5.0, 5.0, 5.0]]])


def test_scores_match_sklearn():
    from sklearn.ensemble import IsolationForest

    data = _data()
    scores, flags = novelty_scores(data, n_estimators=50, contamination=0.1, random_state=0)
    model = IsolationForest(n_estimators=50, contamination=0.1, random_state=0).fit(data)
    assert np.allclose(scores, model.decision_function(data))
    assert np.array_equal(flags, model.predict(data))
    assert flags[-1] == -1


def test_run_writes_rows():
    data = _data()
    form = Form(
        data=data.astype(np.float32),
        dims=["sequence", "embedding"],
        labels={"sequence": {f"s{i}": i for i in range(len(data))}, "embedding": {f"f{i}": i for i in range(3)}},
        info={"missing_code": np.nan},
    )
    ctx = Context("/tmp/bp287", {"params": {}})
    ctx["embeddings"] = form
    run(ctx, [{"name": "esm_embedding_isolation_forest", "inputs": ["embeddings"], "params": {"output": "novelty"}}])
    result = ctx["novelty"]
    assert result.data.shape == (len(data), 2)
    assert result.info["n_outliers"] >= 1


def test_errors():
    with pytest.raises(StepError, match="at least four samples"):
        novelty_scores(np.ones((3, 2)))
    with pytest.raises(StepError, match="contamination must be"):
        novelty_scores(np.ones((6, 2)), contamination=0.0)
