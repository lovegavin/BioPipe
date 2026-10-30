"""Shared helpers for binary-outcome clinical prediction operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._stats21_common import numeric_column, table_frame


def binary_prediction_table(form, sample_dim: str, feature_dim: str, outcome_label: str, *risk_labels: str, label: str):
    """Decode a table and return finite binary truth plus risk columns."""
    frame = table_frame(form, sample_dim, feature_dim, label)
    outcome = numeric_column(frame, outcome_label, label)
    risks = [numeric_column(frame, name, label) for name in risk_labels]
    keep = np.isfinite(outcome)
    for risk in risks:
        keep &= np.isfinite(risk)
    outcome = outcome[keep]
    risks = [risk[keep] for risk in risks]
    if outcome.size < 4:
        raise StepError(f"{label}: at least 4 complete observations are required")
    if not np.all(np.isin(outcome, (0.0, 1.0))):
        raise StepError(f"{label}: outcome must be binary 0/1")
    events = int(np.sum(outcome == 1.0))
    if events < 1 or events >= outcome.size:
        raise StepError(f"{label}: both outcome classes are required")
    for name, risk in zip(risk_labels, risks):
        if np.any(risk < 0.0) or np.any(risk > 1.0):
            raise StepError(f"{label}: {name} must lie in [0, 1]")
    return outcome, risks
