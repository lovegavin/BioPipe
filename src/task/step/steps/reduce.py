# src/task/step/steps/reduce.py
"""Dimensionality reduction along one axis of a form.

Compresses one axis of a 2D form into a small number of components.
The other axis becomes the observation axis of the output.

Two kinds of input
------------------
1. Feature matrix ``[feature, sample]`` (or the reverse). The
   operator compresses the feature axis into components. Methods:
   ``pca``, ``umap``, ``tsne``.

2. Square distance matrix ``[sample, sample_b]`` (produced by
   ``distance_matrix``). The operator computes principal coordinates
   of the distance matrix. Method: ``pcoa``.

The output always has the form::

    dims = [<observation_dim>, "component"]

Output component labels
-----------------------
    pca   -> "PC1", "PC2", ...
    pcoa  -> "PCo1", "PCo2", ...
    umap  -> "UMAP1", "UMAP2", ...
    tsne  -> "tSNE1", "tSNE2", ...

Standardization
---------------
For ``pca`` / ``umap`` / ``tsne``, ``standardize=True`` (default)
divides each feature by its standard deviation after centering.
For ``pcoa``, standardization does not apply and is ignored.

Missing values
--------------
Feature matrix: missing cells are filled with the feature mean
before any standardization.
Distance matrix: missing cells are treated as 0, and the double
centering handles the rest.

Params:
    dim            : dim to compress, or the first axis of a
                     distance matrix (required)
    method         : "pca" | "umap" | "tsne" | "pcoa"
                     (default "pca")
    n_components   : number of components to keep
                     (pca=10, umap=2, tsne=2, pcoa=10)
    standardize    : z-score features before reducing, only for
                     pca / umap / tsne (default True)
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
from src.task.step.steps._microbiome import CONTRACTS, SCHEMAS, estimate, metadata


_METHODS = ("pca", "umap", "tsne", "pcoa")
_DEFAULT_COMPONENTS = {"pca": 10, "umap": 2, "tsne": 2, "pcoa": 10}
_COMPONENT_PREFIX = {
    "pca": "PC",
    "pcoa": "PCo",
    "umap": "UMAP",
    "tsne": "tSNE",
}


class ReduceStep(Step):
    """Reduce one axis of a 2D form to a small number of components."""
    dependencies = ['scikit-learn>=1.5', 'umap-learn>=0.5']
    dependency_imports = ['sklearn', 'umap']

    name = "reduce"
    inputs_arity = 1
    outputs = []
    title = 'PCA / PCoA / UMAP / t-SNE'
    category = "Microbiome"
    builtin_package = "biopipe-microbiome"
    legacy_parameters = False
    parameters_schema = SCHEMAS['reduce']
    input_contracts, output_contract = CONTRACTS['reduce']
    output_parameter = "output"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

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

        is_distance = _looks_like_distance(form, dim)

        if method == "pcoa":
            if not is_distance:
                raise StepError(
                    f"reduce/pcoa: input must be a square distance "
                    f"matrix with dims ['{dim}', '{dim}_b'], got "
                    f"{form.dims}"
                )
            scores, explained = self._run_pcoa(
                form, dim, n_components
            )
        else:
            if is_distance:
                raise StepError(
                    f"reduce/{method}: input looks like a distance "
                    f"matrix (dims {form.dims}); use method='pcoa' "
                    f"for distance matrices"
                )
            scores, explained, _ = self._run_feature(
                form, dim, method, n_components,
                standardize, random_state, ctx.step_params,
            )

        prefix = _COMPONENT_PREFIX[method]
        k = scores.shape[1]
        obs_dim_name = form.dims[0] if is_distance else \
            form.dims[1 - form.dims.index(dim)]

        out_labels = {
            obs_dim_name: dict(form.labels[obs_dim_name]),
            "component": {f"{prefix}{i + 1}": i for i in range(k)},
        }

        out_info, out_axes = metadata(form, [obs_dim_name], "scores")
        ctx[out_name] = Form(
            data=scores.astype(np.float32),
            dims=[obs_dim_name, "component"],
            labels=out_labels,
            info=out_info,
            axis_info=out_axes,
        )

        self._export_data = {
            "dim": dim,
            "method": method,
            "input_kind": "distance" if is_distance else "features",
            "n_components": k,
            "n_observations": int(scores.shape[0]),
            "explained_variance_ratio": (
                [float(v) for v in explained]
                if explained is not None else None
            ),
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "dim": dim,
            "n_components": k,
        }

        if method == "pcoa":
            msg = (
                f"[reduce] method='pcoa' dim='{dim}' -> {k} "
                f"component{'s' if k != 1 else ''}"
            )
            if k >= 1:
                msg += f", PCo1={explained[0]:.3f}"
            if k >= 2:
                msg += f", PCo2={explained[1]:.3f}"
            print(msg)
        elif method == "pca":
            msg = (
                f"[reduce] method='pca' dim='{dim}' -> {k} "
                f"component{'s' if k != 1 else ''}"
            )
            if k >= 1:
                msg += f", PC1={explained[0]:.3f}"
            if k >= 2:
                msg += f", PC2={explained[1]:.3f}"
            print(msg)
        else:
            print(
                f"[reduce] method='{method}' dim='{dim}' -> {k} "
                f"component{'s' if k != 1 else ''}, "
                f"{scores.shape[0]} observations"
            )

    def export(self, ctx: Context) -> dict:
        return self._export_data

    # ------------------------------------------------------------------ #
    # Feature matrix pipeline
    # ------------------------------------------------------------------ #

    def _run_feature(self, form, dim, method, n_components,
                     standardize, random_state, params):
        compress_axis = form.dims.index(dim)
        other_axis = 1 - compress_axis
        X = np.moveaxis(form.data, other_axis, 0).astype(np.float64)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(X)
        else:
            missing = X == missing_code

        with np.errstate(invalid="ignore"):
            col_mean = np.nanmean(
                np.where(missing, np.nan, X), axis=0
            )
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)

        filled = np.where(missing, col_mean, X)
        centered = filled - col_mean

        if standardize:
            with np.errstate(invalid="ignore"):
                col_std = np.nanstd(
                    np.where(missing, np.nan, X), axis=0
                )
            col_std = np.where(
                np.isfinite(col_std) & (col_std > 1e-12),
                col_std, 1.0,
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
            scores = _umap(scaled, k, random_state, params)
            explained = None
            singular = None
        else:  # tsne
            scores = _tsne(scaled, k, random_state, params)
            explained = None
            singular = None

        return scores, explained, singular

    # ------------------------------------------------------------------ #
    # PCoA pipeline
    # ------------------------------------------------------------------ #

    def _run_pcoa(self, form, dim, n_components):
        n = form.data.shape[0]
        if form.data.shape[1] != n:
            raise StepError(
                f"reduce/pcoa: distance matrix must be square, got "
                f"{form.data.shape}"
            )
        D = form.data.astype(np.float64)

        # Symmetrize and zero diagonal to be robust to rounding.
        D = 0.5 * (D + D.T)
        np.fill_diagonal(D, 0.0)

        # Gower's double centering.
        D2 = D ** 2
        J = np.eye(n) - np.ones((n, n)) / n
        B = -0.5 * J @ D2 @ J
        # Enforce symmetry in case of rounding.
        B = 0.5 * (B + B.T)

        eigvals, eigvecs = np.linalg.eigh(B)
        # Sort descending.
        order = np.argsort(eigvals)[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]

        # Keep only positive eigenvalues.
        positive = eigvals > 1e-10
        if not positive.any():
            raise StepError(
                "reduce/pcoa: no positive eigenvalues; the distance "
                "matrix does not admit a real PCoA solution"
            )
        eigvals = eigvals[positive]
        eigvecs = eigvecs[:, positive]

        total = float(eigvals.sum())
        k = min(n_components, eigvals.size)
        coords = eigvecs[:, :k] * np.sqrt(eigvals[:k])
        explained = eigvals[:k] / total if total > 0 else \
            np.zeros(k)

        return coords, explained


# ---------------------------------------------------------------------- #
# Look-like check
# ---------------------------------------------------------------------- #

def _looks_like_distance(form: Form, dim: str) -> bool:
    """Return True if the form looks like a square distance matrix
    produced by distance_matrix."""
    if form.data.ndim != 2:
        return False
    if form.data.shape[0] != form.data.shape[1]:
        return False
    if form.dims[0] != dim:
        return False
    if form.dims[1] != f"{dim}_b":
        return False
    # Labels must match on both axes.
    return form.labels[dim] == form.labels[f"{dim}_b"]


# ---------------------------------------------------------------------- #
# Feature methods
# ---------------------------------------------------------------------- #

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
    sig = inspect.signature(TSNE.__init__)
    iter_key = "max_iter" if "max_iter" in sig.parameters else "n_iter"
    kwargs = {
        "n_components": k,
        "perplexity": float(params.get("perplexity", 30.0)),
        "learning_rate": params.get("learning_rate", "auto"),
        "random_state": random_state,
        "init": "pca",
        iter_key: int(params.get("n_iter",
                                 params.get("max_iter", 1000))),
    }
    return TSNE(**kwargs).fit_transform(scaled)