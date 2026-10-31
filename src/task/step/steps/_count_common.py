"""Shared preparation for Poisson and negative-binomial regressions."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import design_matrix, numeric_column, table_frame


def count_design(form, sample_dim: str, feature_dim: str, response_label: str,
                 predictors: list[str], categorical: list[str], label: str):
    """Return (frame, response, design, term names) for a count regression."""
    frame = table_frame(form, sample_dim, feature_dim, label)
    if response_label not in frame.columns:
        raise StepError(f"{label}: response {response_label!r} not found")
    response = numeric_column(frame, response_label, label)
    valid = np.isfinite(response) & (response >= 0)
    for name in predictors:
        if name not in frame.columns:
            raise StepError(f"{label}: predictor {name!r} not found")
        if name in categorical:
            valid &= frame[name].notna().to_numpy()
        else:
            valid &= np.isfinite(numeric_column(frame, name, label))
    frame = frame.loc[valid].reset_index(drop=True)
    response = numeric_column(frame, response_label, label)
    if response.size < 3:
        raise StepError(f"{label}: fewer than three complete rows")
    design, terms = design_matrix(frame, predictors, categorical, label)
    if response.size <= design.shape[1] + 1:
        raise StepError(f"{label}: not enough observations for the model")
    return frame, response, design, terms


def result_rows(params, bse, pvalues, conf, terms: list[str]) -> list[list[float]]:
    rows: list[list[float]] = []
    for i, _term in enumerate(terms):
        coef = float(params[i])
        se = float(bse[i])
        z = coef / se if np.isfinite(se) and se > 0 else float("nan")
        p = float(pvalues[i])
        low, high = float(conf[i, 0]), float(conf[i, 1])
        rows.append([
            coef,
            se,
            z,
            p,
            low,
            high,
            float(np.exp(coef)),
            float(np.exp(low)),
            float(np.exp(high)),
        ])
    return rows
