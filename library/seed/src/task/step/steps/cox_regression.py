# src/task/step/steps/cox_regression.py
"""Cox proportional hazards regression.

Input is a single 2D form with samples as rows and clinical
variables as columns. The operator reads a time column, an event
column, and a set of covariate columns, then fits a Cox proportional
hazards model.

Statistics are delegated to lifelines.CoxPHFitter.

Output form
-----------
    dims    = ["covariate", "statistic"]
    labels  = {covariate: {name: i},
               statistic: {"coef": 0, "HR": 1, "se": 2,
                           "z": 3, "P": 4,
                           "CI_low": 5, "CI_high": 6}}

Categorical covariates
----------------------
String-valued columns (or those encoded by a Reader) are expanded
into one binary column per level, dropping the first level as the
reference. The covariate label in the output is "{col}_{level}".
Numeric columns pass through unchanged.

Params:
    time_label   : column with follow-up time (required)
    event_label  : column with event indicator (required)
    covariates   : list of column names to use as predictors
                   (required)
    categorical  : list of covariate names to treat as categorical;
                   others are used as-is (optional)
    weights_label: optional column with sample weights
    output       : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.forms.metadata import project_metadata


_STAT_LABELS = {
    "coef": 0,
    "HR": 1,
    "se": 2,
    "z": 3,
    "P": 4,
    "CI_low": 5,
    "CI_high": 6,
}


class CoxRegressionStep(Step):
    """Fit a Cox proportional hazards model."""
    provider = 'biopipe-expression'
    parameters_file = 'cox_regression.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'cox_regression',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Cox',
     'description': '多变量比例风险回归',
     'category': '统计分析',
     'icon': 'TrendUp',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2,
                               'labels_axis': [{'axis': 1,
                                                'values': [{'param': 'time_label', 'default': None},
                                                           {'param': 'event_label', 'default': None}]},
                                               {'axis': 1,
                                                'values': {'param': 'covariates', 'default': []}}]}],
                   'output': {'mode': 'cox_regression'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['lifelines<0.31,>=0.30'],
     'dependency_imports': ['lifelines'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    def run(self, ctx: Context, inputs) -> None:
        try:
            from lifelines import CoxPHFitter
            from lifelines.exceptions import (
                ConvergenceError,
            )
        except ImportError as exc:
            raise StepError(
                "cox_regression: lifelines is required. "
                "Install with: pip install lifelines"
            ) from exc

        try:
            from lifelines import CoxPHFitter
        except ImportError as exc:
            raise StepError(
                "cox_regression: lifelines is required."
            ) from exc

        form = inputs[0]
        time_label = ctx.step_params.get("time_label")
        event_label = ctx.step_params.get("event_label")
        covariates = ctx.step_params.get("covariates")
        categorical = list(ctx.step_params.get("categorical", []))
        weights_label = ctx.step_params.get("weights_label")
        out_name = ctx.step_params.get("output", self.name)

        if not time_label:
            raise StepError("cox_regression: 'time_label' is required")
        if not event_label:
            raise StepError("cox_regression: 'event_label' is required")
        if not covariates or not isinstance(covariates, list):
            raise StepError(
                "cox_regression: 'covariates' must be a non-empty list"
            )
        if form.data.ndim != 2:
            raise StepError(
                f"cox_regression: input must be 2D, "
                f"got ndim={form.data.ndim}"
            )

        sample_dim, feature_dim = form.dims[0], form.dims[1]
        feature_labels = form.labels.get(feature_dim, {})

        all_needed = (
            [time_label, event_label] + list(covariates)
            + ([weights_label] if weights_label else [])
        )
        for lbl in all_needed:
            if lbl not in feature_labels:
                raise StepError(
                    f"cox_regression: '{lbl}' not in dim "
                    f"'{feature_dim}'. Available: "
                    f"{sorted(feature_labels)}"
                )

        encoders = form.info.get("encoders", {})
        col_encoders = encoders.get(feature_dim, {})

        def raw_col(lbl):
            return np.take(
                form.data,
                feature_labels[lbl],
                axis=form.dims.index(feature_dim),
            )

        def decode_col(lbl):
            """Return the column as object: strings if encoded,
            otherwise numbers."""
            arr = raw_col(lbl)
            enc = col_encoders.get(lbl)
            if enc is None:
                return arr.astype(float)
            return np.array(
                [
                    enc.inverse.get(int(v), None)
                    if np.isfinite(v) else None
                    for v in arr
                ],
                dtype=object,
            )

        times = raw_col(time_label).astype(float)
        events = raw_col(event_label).astype(float)

        sample_labels = form.labels[sample_dim]
        pos_to_sample = {v: k for k, v in sample_labels.items()}

        # Build a pandas DataFrame of usable rows.
        records: dict[str, list] = {
            "_sample": [],
            "_time": [],
            "_event": [],
        }
        for c in covariates:
            records[c] = []
        if weights_label:
            records["_weight"] = []

        for i in range(times.shape[0]):
            t = times[i]
            e = events[i]
            if not (np.isfinite(t) and np.isfinite(e)):
                continue
            if t <= 0:
                continue

            row_ok = True
            row_vals: dict = {}
            for c in covariates:
                v = decode_col(c)[i]
                if v is None:
                    row_ok = False
                    break
                if isinstance(v, float) and not np.isfinite(v):
                    row_ok = False
                    break
                row_vals[c] = v
            if not row_ok:
                continue

            records["_sample"].append(
                pos_to_sample.get(i, f"#{i}")
            )
            records["_time"].append(float(t))
            records["_event"].append(int(e))
            for c in covariates:
                records[c].append(row_vals[c])
            if weights_label:
                records["_weight"].append(
                    float(raw_col(weights_label)[i])
                )

        if len(records["_time"]) == 0:
            raise StepError(
                "cox_regression: no usable rows after dropping "
                "missing values"
            )
        if len(records["_time"]) < 5:
            raise StepError(
                f"cox_regression: only {len(records['_time'])} usable "
                f"rows; need at least 5"
            )

        df = pd.DataFrame(records).set_index("_sample")
        df = df.rename(columns={"_time": "T", "_event": "E"})

        # Build the design matrix.
        design_parts = []
        for c in covariates:
            col = df[c]
            if c in categorical:
                dummies = pd.get_dummies(
                    col.astype(str), prefix=c, drop_first=True,
                    dtype=float,
                )
                design_parts.append(dummies)
            else:
                design_parts.append(
                    pd.DataFrame({c: col.astype(float)},
                                 index=df.index)
                )
        design = pd.concat(design_parts, axis=1)

        fit_df = pd.concat(
            [df[["T", "E"]], design], axis=1
        )
        if weights_label:
            fit_df["_weight"] = df["_weight"]

        # Constant column check.
        constant_cols = [
            c for c in design.columns
            if design[c].std() < 1e-12
        ]
        if constant_cols:
            raise StepError(
                f"cox_regression: covariate(s) are constant: "
                f"{constant_cols}"
            )

        cph = CoxPHFitter()
        try:
            cph.fit(
                fit_df,
                duration_col="T",
                event_col="E",
                weights_col="_weight" if weights_label else None,
                robust=False,
            )
        except Exception as exc:
            raise StepError(
                f"cox_regression: fit failed: {exc}"
            ) from exc

        summary = cph.summary
        coef_names = list(summary.index)
        n_rows = len(coef_names)

        data = np.zeros((n_rows, 7), dtype=np.float32)
        per_row = []
        for i, name in enumerate(coef_names):
            row = summary.loc[name]
            coef = float(row["coef"])
            hr = float(np.exp(coef))
            se = float(row["se(coef)"])
            z = float(row["z"])
            p = float(row["p"])
            ci_low = float(row["coef lower 95%"])
            ci_high = float(row["coef upper 95%"])
            data[i] = [
                coef, hr, se, z, p,
                float(np.exp(ci_low)),
                float(np.exp(ci_high)),
            ]
            per_row.append({
                "covariate": str(name),
                "coef": coef,
                "HR": hr,
                "se": se,
                "z": z,
                "P": p,
                "CI_low": float(np.exp(ci_low)),
                "CI_high": float(np.exp(ci_high)),
            })

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info.update(missing_code=np.nan, representation="cox_regression")
        ctx[out_name] = Form(
            data=data,
            dims=["covariate", "statistic"],
            labels={
                "covariate": {n: i for i, n in enumerate(coef_names)},
                "statistic": dict(_STAT_LABELS),
            },
            info=info,
            axis_info=axis_info,
        )

        self._export_data = {
            "kind": "cox_regression",
            "time_label": time_label,
            "event_label": event_label,
            "covariates": list(covariates),
            "categorical": list(categorical),
            "n_samples": int(len(fit_df)),
            "n_events": int(fit_df["E"].sum()),
            "concordance_index": float(cph.concordance_index_),
            "log_likelihood": float(cph.log_likelihood_),
            "aic": float(cph.AIC_partial_),
            "results": per_row,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_samples": int(len(fit_df)),
            "n_events": int(fit_df["E"].sum()),
            "n_covariates": n_rows,
            "concordance_index": float(cph.concordance_index_),
        }

        print(
            f"[cox_regression] {n_rows} covariates, "
            f"n={len(fit_df)}, events={int(fit_df['E'].sum())}, "
            f"C-index={cph.concordance_index_:.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data