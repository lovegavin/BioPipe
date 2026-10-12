# src/task/step/steps/reduce.py
"""Dimensionality reduction along one axis of a form.

Compresses one axis of a 2D form into a small number of components.
The other axis becomes the observation axis of the output.

Layout
------
    input  dims: [<dim>, <other>]   (any orientation)
    output dims: [<other>, "component"]

Methods
-------
    pca     principal component analysis via SVD (numpy)
    umap    uniform manifold approximation and projection
    tsne    t-distributed stochastic neighbor embedding

The operator works on any 2D form. Missing cells are filled with the
column mean before any standardization. The output carries no
missing values.

Standardization
---------------
``standardize=True`` (default) divides each feature by its standard
deviation after centering, so all features contribute equally. Set
to False to keep the raw scale.

Params:
    dim            : dim to compress (required)
    method         : "pca" | "umap" | "tsne" (default "pca")
    n_components   : number of output components (method default:
                     pca=10, umap=2, tsne=2)
    standardize    : z-score features before reducing (default True)
    random_state   : random seed for umap / tsne (default 0)
    output         : context key for the result (default: step name)

Method-specific parameters are forwarded as-is:
    umap: n_neighbors, min_dist, metric
    tsne: perplexity, learning_rate, n_iter
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_METHODS = ("pca", "umap", "tsne")
_DEFAULT_COMPONENTS = {"pca": 10, "umap": 2, "tsne": 2}


class ReduceStep(Step):
    """Reduce one axis of a 2D form to a small number of components."""

    name = "reduce"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        method = ctx.step_params.get("method", "pca")
        n_components = ctx.step_params.get("n_components")
        standardize = bool(ctx.step_params.get("standardize", True))
        random_state = int(ctx.step_params.get("random_state", 0))
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("reduce: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"reduce: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if method not in _METHODS:
            raise StepError(
                f"reduce: method must be one of {list(_METHODS)}, "
                f"got {method!r}"
            )
        if form.data.ndim != 2:
            raise StepError(
                f"reduce: input must be 2D, got ndim={form.data.ndim}"
            )

        if n_components is None:
            n_components = _DEFAULT_COMPONENTS[method]
        n_components = int(n_components)
        if n_components < 1:
            raise StepError(
                f"reduce: n_components must be >= 1, "
                f"got {n_components}"
            )

        compress_axis = form.dims.index(dim)
        other_axis = 1 - compress_axis
        X = np.moveaxis(form.data, other_axis, 0).astype(np.float64)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(X)
        else:
            missing = X == missing_code

        with np.errstate(invalid="ignore"):
            col_mean = np.nanmean(np.where(missing, np.nan, X), axis=0)
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)

        filled = np.where(missing, col_mean, X)
        centered = filled - col_mean

        if standardize:
            with np.errstate(invalid="ignore"):
                col_std = np.nanstd(
                    np.where(missing, np.nan, X), axis=0
                )
            col_std = np.where(
                np.isfinite(col_std) & (col_std > 1e-12), col_std, 1.0
            )
            scaled = centered / col_std
        else:
            scaled = centered

        n_samples, n_features = scaled.shape
        k_max = min(n_samples, n_features)
        k = min(n_components, k_max)
        if k < 1:
            raise StepError(
                f"reduce: input has shape {scaled.shape}, "
                f"cannot produce any component"
            )

        if method == "pca":
            scores, explained, singular = _pca(scaled, k)
        elif method == "umap":
            scores = _umap(
                scaled, k, random_state, ctx.step_params
            )
            explained = None
            singular = None
        else:  # tsne
            scores = _tsne(
                scaled, k, random_state, ctx.step_params
            )
            explained = None
            singular = None

        obs_dim_name = form.dims[other_axis]
        out_labels = {
            obs_dim_name: dict(form.labels[obs_dim_name]),
            "component": {f"PC{i + 1}": i for i in range(k)},
        }

        ctx[out_name] = Form(
            data=scores.astype(np.float32),
            dims=[obs_dim_name, "component"],
            labels=out_labels,
            info={},
        )

        self._export_data = {
            "dim": dim,
            "method": method,
            "standardize": standardize,
            "n_components": k,
            "n_observations": int(scores.shape[0]),
            "n_features": int(scaled.shape[1]),
            "explained_variance_ratio": (
                [float(v) for v in explained]
                if explained is not None else None
            ),
            "singular_values": (
                [float(v) for v in singular]
                if singular is not None else None
            ),
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "dim": dim,
            "n_components": k,
        }

        if method == "pca":
            print(
                f"[reduce] method='pca' dim='{dim}' -> {k} components, "
                f"PC1={explained[0]:.3f}, PC2={explained[1]:.3f}"
            )
        else:
            print(
                f"[reduce] method='{method}' dim='{dim}' -> {k} "
                f"components, {scores.shape[0]} observations"
            )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _pca(scaled: np.ndarray, k: int):
    U, S, _ = np.linalg.svd(scaled, full_matrices=False)
    scores = U[:, :k] * S[:k]
    total = float((S ** 2).sum())
    explained = (S[:k] ** 2) / total if total > 0 else np.zeros(k)
    return scores, explained, S[:k]


def _umap(scaled: np.ndarray, k: int, random_state: int,
          params: dict) -> np.ndarray:
    try:
        import umap
    except ImportError as exc:
        raise StepError(
            "reduce/umap: umap-learn is required. "
            "Install with: pip install umap-learn"
        ) from exc

    reducer = umap.UMAP(
        n_components=k,
        n_neighbors=int(params.get("n_neighbors", 15)),
        min_dist=float(params.get("min_dist", 0.1)),
        metric=params.get("metric", "euclidean"),
        random_state=random_state,
    )
    return reducer.fit_transform(scaled)


def _tsne(scaled: np.ndarray, k: int, random_state: int,
          params: dict) -> np.ndarray:
    try:
        from sklearn.manifold import TSNE
        import inspect
    except ImportError as exc:
        raise StepError(
            "reduce/tsne: scikit-learn is required. "
            "Install with: pip install scikit-learn"
        ) from exc

    # scikit-learn 1.5 renamed n_iter -> max_iter.
    sig = inspect.signature(TSNE.__init__)
    iter_key = "max_iter" if "max_iter" in sig.parameters else "n_iter"

    kwargs = {
        "n_components": k,
        "perplexity": float(params.get("perplexity", 30.0)),
        "learning_rate": params.get("learning_rate", "auto"),
        "random_state": random_state,
        "init": "pca",
        iter_key: int(params.get("n_iter", params.get("max_iter", 1000))),
    }
    tsne = TSNE(**kwargs)
    return tsne.fit_transform(scaled)