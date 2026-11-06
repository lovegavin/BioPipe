from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.ml_learning_curve import MlLearningCurveStep
from src.task.step.steps.ml_grid_search import MlGridSearchStep
from src.task.step.steps.stats_fdr import StatsFdrStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _features(X):
    n = X.shape[0]
    return Form(X, dims=['sample', 'feature'],
                labels={'sample': {f'S{i:03d}': i for i in range(n)},
                        'feature': {f'f{j}': j for j in range(X.shape[1])}})


def _labels(y):
    return Form(np.asarray(y, dtype=float).reshape(-1, 1), dims=['sample', 'label'],
                labels={'sample': {f'S{i:03d}': i for i in range(len(y))},
                        'label': {'label': 0}})


def _pvalues(p):
    return Form(np.asarray(p, dtype=float).reshape(-1, 1), dims=['test', 'pvalue'],
                labels={'test': {f't{i}': i for i in range(len(p))}, 'pvalue': {'p': 0}})


def _data(seed=0, n=60):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 2))
    y = (X[:, 0] + 0.3 * X[:, 1] > 0).astype(int)
    return X, y


def _run(step, inputs, params):
    ctx = Ctx({'output': 'out', **params})
    step.run(ctx, inputs)
    return ctx, ctx['out']


def test_learning_curve_sizes_and_shape():
    X, y = _data()
    ctx, out = _run(MlLearningCurveStep(), [_features(X), _labels(y)],
                    {'train_sizes': '0.25,0.5,1.0', 'n_splits': 5, 'seed': 0,
                     'standardize': True, 'metric': 'accuracy'})
    assert out.data.shape == (3, 5)
    assert out.data[:, 0].tolist() == [12.0, 24.0, 48.0]
    assert np.all(out.data[:, 3] >= 0) and np.all(out.data[:, 3] <= 1)
    assert ctx['out'].info['n_splits'] == 5


def test_learning_curve_roc_auc_and_standardize_false():
    X, y = _data(seed=1)
    ctx, out = _run(MlLearningCurveStep(), [_features(X), _labels(y)],
                    {'train_sizes': '0.5,1.0', 'standardize': False,
                     'metric': 'roc_auc'})
    assert out.data.shape[0] == 2
    assert 0.0 <= out.data[0, 3] <= 1.0


def test_learning_curve_rejects_bad_fraction():
    X, y = _data()
    with pytest.raises(StepError, match='train_sizes'):
        _run(MlLearningCurveStep(), [_features(X), _labels(y)],
             {'train_sizes': ' , ', 'n_splits': 5})


def test_grid_search_picks_best_and_reports():
    X, y = _data(seed=2)
    ctx, out = _run(MlGridSearchStep(), [_features(X), _labels(y)],
                    {'C_values': '0.01,1,100', 'n_splits': 5, 'seed': 0})
    assert out.data.shape == (3, 3)
    assert out.info['best_C'] in (0.01, 1.0, 100.0)
    best = max(out.data, key=lambda row: row[1])
    assert out.info['best_C'] == pytest.approx(best[0])


def test_grid_search_rejects_mismatched_rows():
    X, _ = _data()
    y = np.array([0, 1] * (X.shape[0] // 4), dtype=int)
    with pytest.raises(StepError, match='differ'):
        _run(MlGridSearchStep(), [_features(X), _labels(y)], {'C_values': '1'})


def test_fdr_bh_known_values():
    _, out = _run(StatsFdrStep(), [_pvalues([0.01, 0.04, 0.03, 0.2])],
                  {'method': 'bh', 'alpha': 0.05})
    # sorted ranks 1..4 give raw 0.04, 0.06, 0.0533..., 0.8; reverse min makes
    # the middle two 0.0533...
    np.testing.assert_allclose(out.data[:, 1], [0.04, 0.05333333333333334,
                                                0.05333333333333334, 0.2], rtol=1e-12)
    assert out.data[:, 2].tolist() == [1.0, 0.0, 0.0, 0.0]


def test_fdr_holm_and_bonferroni():
    _, holm = _run(StatsFdrStep(), [_pvalues([0.01, 0.02, 0.03, 0.04])], {'method': 'holm'})
    np.testing.assert_allclose(holm.data[:, 1], [0.04, 0.06, 0.06, 0.06], atol=1e-15)
    _, bonf = _run(StatsFdrStep(), [_pvalues([0.01, 0.6])], {'method': 'bonferroni'})
    np.testing.assert_allclose(bonf.data[:, 1], [0.02, 1.0])


def test_fdr_by_is_bh_times_harmonic():
    p = [0.01, 0.02, 0.03, 0.04]
    _, bh = _run(StatsFdrStep(), [_pvalues(p)], {'method': 'bh', 'alpha': 0.5})
    _, by = _run(StatsFdrStep(), [_pvalues(p)], {'method': 'by', 'alpha': 0.5})
    harmonic = sum(1.0 / i for i in range(1, 5))
    np.testing.assert_allclose(by.data[:, 1], np.minimum(1.0, bh.data[:, 1] * harmonic), rtol=1e-12)


def test_fdr_rejects_invalid_pvalue():
    with pytest.raises(StepError, match='within'):
        _run(StatsFdrStep(), [_pvalues([0.2, 1.5])], {'method': 'bh'})
