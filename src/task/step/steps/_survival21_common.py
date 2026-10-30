"""Shared Cox/Brier helpers for 0.23 survival operators."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import StepError


def survival_columns(form, sample_dim: str, feature_dim: str, time_label: str,
                     event_label: str, risk_label: str):
    if form.data.ndim != 2:
        raise StepError("survival input must be 2D")
    if sample_dim not in form.dims or feature_dim not in form.dims:
        raise StepError(f"expected dims {sample_dim!r}, {feature_dim!r}, got {form.dims}")
    labels = form.labels.get(feature_dim, {})
    for key in (time_label, event_label, risk_label):
        if key not in labels:
            raise StepError(f"column {key!r} not in {sorted(labels)}")
    data = np.asarray(form.data, dtype=np.float64)
    if form.dims.index(sample_dim) == 1:
        data = data.T
    times = data[:, labels[time_label]]
    events = data[:, labels[event_label]]
    risk = data[:, labels[risk_label]]
    keep = np.isfinite(times) & np.isfinite(events) & np.isfinite(risk)
    keep &= times > 0
    keep &= np.isin(events, (0, 1))
    times, events, risk = times[keep], events.astype(int)[keep], risk[keep]
    if times.size < 4:
        raise StepError("fewer than four usable survival samples")
    if np.unique(risk).size < 2:
        raise StepError("risk score must have at least two distinct values")
    return times, events, risk


def fit_cox(times, events, risk):
    from lifelines import CoxPHFitter

    df = pd.DataFrame({"time": times, "event": events, "risk": risk})
    try:
        cph = CoxPHFitter()
        cph.fit(df, duration_col="time", event_col="event")
    except Exception as exc:
        raise StepError(f"Cox model fit failed: {exc}") from exc
    return cph, df


def km_survival(times, events, t: float) -> float:
    survival = 1.0
    for at in np.unique(times[times <= t]):
        n = int(np.sum(times >= at))
        d = int(np.sum((times == at) & (events == 1)))
        if n > 0:
            survival *= 1.0 - d / n
    return float(survival)


def cox_brier(cph, df, times, events, risk, eval_times):
    """R survival::brier equivalent, using CoxPH predictions from lifelines."""
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=int)
    risk = np.asarray(risk, dtype=float)
    eval_times = np.asarray(eval_times, dtype=float)
    if np.any(~np.isfinite(eval_times)) or np.any(eval_times <= 0):
        raise StepError("evaluation times must be finite and > 0")
    if np.unique(times).size < 2:
        raise StepError("at least two distinct survival times are required")
    mindiff = float(np.min(np.diff(np.unique(times))))
    dtime = times + np.where(events == 0, mindiff / 2.0, 0.0)
    censoring = 1 - events
    pred = cph.predict_survival_function(df, times=eval_times)
    # pred: index=times, columns=samples
    p1 = 1.0 - pred.to_numpy().T  # sample x evaluation time
    rows = []
    for j, t in enumerate(eval_times):
        g = np.asarray([km_survival(dtime, censoring, min(float(d), float(t))) for d in dtime])
        if np.any(g <= 0) or np.any(~np.isfinite(g)):
            raise StepError("censoring survival is zero at an evaluation time")
        wt = np.where((dtime < t) & (events == 0), 0.0, 1.0 / g)
        b1 = np.where(dtime > t, p1[:, j] ** 2, (events - p1[:, j]) ** 2)
        denom = float(np.sum(wt))
        if denom <= 0:
            raise StepError("no positive Brier weights at an evaluation time")
        rows.append(float(np.sum(wt * b1) / denom))
    return np.asarray(rows, dtype=float)
