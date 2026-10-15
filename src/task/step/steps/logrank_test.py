# src/task/step/steps/logrank_test.py
"""Log-rank test on survival data grouped by a label column.

Compares survival distributions across groups. Statistics are
delegated to lifelines:

    multivariate_logrank_test   overall test across all groups
    logrank_test                pairwise test between two groups

Input is a single 2D form with samples as rows and clinical
variables as columns.

Output form
-----------
    dims    = ["comparison", "statistic"]
    labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
               statistic: {"chi2": 0, "df": 1, "P": 2}}

Params:
    time_label   : follow-up time (required)
    event_label  : event indicator, 1 = event, 0 = censored (required)
    group_label  : group assignment (required)
    group_map    : optional dict {raw: display} to remap group values
    groups       : optional list of group names to keep, in order
    pairwise     : also run pairwise comparisons (default False,
                   only used when there are >= 3 groups)
    output       : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.core.forms.metadata import project_metadata


_STAT_LABELS = {"chi2": 0, "df": 1, "P": 2}


class LogrankTestStep(Step):
    """Log-rank test for survival differences across groups."""
    dependencies = ['lifelines>=0.30,<0.31']
    dependency_imports = ['lifelines']

    name = "logrank_test"
    inputs_arity = 1
    outputs = []
    input_contracts = [{**port(ndim=2), "labels_axis": [{"axis": 1, "values": [param("time_label"), param("event_label"), param("group_label")]}]}]
    output_contract = {"mode": "logrank_test"}
    output_parameter = "output"

    def run(self, ctx: Context, inputs) -> None:
        try:
            from lifelines.statistics import (
                logrank_test as _pairwise_test,
            )
            from lifelines.statistics import (
                multivariate_logrank_test as _overall_test,
            )
        except ImportError as exc:
            raise StepError(
                "logrank_test: lifelines is required. "
                "Install with: pip install lifelines"
            ) from exc

        form = inputs[0]
        time_label = ctx.step_params.get("time_label")
        event_label = ctx.step_params.get("event_label")
        group_label = ctx.step_params.get("group_label")
        group_map = ctx.step_params.get("group_map")
        groups_arg = ctx.step_params.get("groups")
        pairwise = bool(ctx.step_params.get("pairwise", False))
        out_name = ctx.step_params.get("output", self.name)

        for name, v in (
            ("time_label", time_label),
            ("event_label", event_label),
            ("group_label", group_label),
        ):
            if not v:
                raise StepError(f"logrank_test: '{name}' is required")
        if form.data.ndim != 2:
            raise StepError(
                f"logrank_test: input must be 2D, got ndim={form.data.ndim}"
            )

        group_map_norm: dict[str, str] = {}
        if group_map is not None:
            if not isinstance(group_map, dict):
                raise StepError(
                    f"logrank_test: 'group_map' must be a dict, "
                    f"got {type(group_map).__name__}"
                )
            for k, v in group_map.items():
                group_map_norm[str(k)] = str(v)

        sample_dim, feature_dim = form.dims[0], form.dims[1]
        labels = form.labels.get(feature_dim, {})
        for lbl, name in (
            (time_label, "time_label"),
            (event_label, "event_label"),
            (group_label, "group_label"),
        ):
            if lbl not in labels:
                raise StepError(
                    f"logrank_test: {name}='{lbl}' not in dim "
                    f"'{feature_dim}'. Available: {sorted(labels)}"
                )

        def col(lbl):
            return np.take(
                form.data,
                labels[lbl],
                axis=form.dims.index(feature_dim),
            )

        times = col(time_label).astype(float)
        events = col(event_label).astype(float)
        groups_raw = col(group_label)

        encoders = form.info.get("encoders", {})
        encoder = None
        if feature_dim in encoders and group_label in encoders[feature_dim]:
            encoder = encoders[feature_dim][group_label]

        # Collect valid samples.
        by_group: dict[str, list[tuple[float, int]]] = {}
        for i in range(times.shape[0]):
            t = times[i]
            e = events[i]
            if not (np.isfinite(t) and np.isfinite(e)):
                continue
            if t < 0:
                continue
            name = _decode(groups_raw[i], encoder)
            if name is None:
                continue
            name = group_map_norm.get(name, name)
            by_group.setdefault(name, []).append((float(t), int(e)))

        if not by_group:
            raise StepError(
                "logrank_test: no samples with valid time, event and "
                "group values"
            )

        if groups_arg is not None:
            if not isinstance(groups_arg, list) or not groups_arg:
                raise StepError(
                    "logrank_test: 'groups' must be a non-empty list"
                )
            missing = [g for g in groups_arg if g not in by_group]
            if missing:
                raise StepError(
                    f"logrank_test: groups not found: {missing}. "
                    f"Available: {sorted(by_group)}"
                )
            group_order = list(groups_arg)
        else:
            group_order = sorted(by_group.keys())

        if len(group_order) < 2:
            raise StepError(
                f"logrank_test: need at least 2 groups, got "
                f"{len(group_order)}"
            )

        # Flatten data for lifelines.
        all_times: list[float] = []
        all_events: list[int] = []
        all_groups: list[str] = []
        groups_summary: dict[str, dict] = {}
        for g in group_order:
            samples = by_group[g]
            n = len(samples)
            n_events = sum(1 for _, e in samples if e == 1)
            groups_summary[g] = {"n": n, "n_events": n_events}
            for t, e in samples:
                all_times.append(t)
                all_events.append(e)
                all_groups.append(g)

        t_arr = np.asarray(all_times, dtype=float)
        e_arr = np.asarray(all_events, dtype=int)
        g_arr = np.asarray(all_groups, dtype=object)

        # Overall test.
        overall = _overall_test(
            t_arr, g_arr, event_observed=e_arr
        )
        overall_chi2 = float(overall.test_statistic)
        overall_p = float(overall.p_value)
        overall_df = len(group_order) - 1

        rows: list[tuple[str, float, int, float]] = [
            ("overall", overall_chi2, overall_df, overall_p),
        ]

        # Pairwise (only if requested and >= 3 groups).
        pairwise_records: list[dict] = []
        if pairwise and len(group_order) >= 3:
            for i in range(len(group_order)):
                for j in range(i + 1, len(group_order)):
                    g1 = group_order[i]
                    g2 = group_order[j]
                    m1 = g_arr == g1
                    m2 = g_arr == g2
                    res = _pairwise_test(
                        t_arr[m1], t_arr[m2],
                        event_observed_A=e_arr[m1],
                        event_observed_B=e_arr[m2],
                    )
                    label = f"{g1} vs {g2}"
                    chi2 = float(res.test_statistic)
                    pval = float(res.p_value)
                    rows.append((label, chi2, 1, pval))
                    pairwise_records.append({
                        "comparison": label,
                        "chi2": chi2,
                        "df": 1,
                        "P": pval,
                        "n_a": int(m1.sum()),
                        "n_b": int(m2.sum()),
                    })

        # Build output Form.
        data = np.array(
            [[r[1], r[2], r[3]] for r in rows], dtype=np.float32
        )
        comp_labels = {r[0]: i for i, r in enumerate(rows)}
        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info.update(missing_code=np.nan, representation="logrank_test")
        ctx[out_name] = Form(
            data=data,
            dims=["comparison", "statistic"],
            labels={
                "comparison": comp_labels,
                "statistic": dict(_STAT_LABELS),
            },
            info=info,
            axis_info=axis_info,
        )

        self._export_data = {
            "kind": "logrank_test",
            "time_label": time_label,
            "event_label": event_label,
            "group_label": group_label,
            "group_map": group_map_norm if group_map_norm else None,
            "groups": group_order,
            "n_total": int(t_arr.size),
            "n_events": int((e_arr == 1).sum()),
            "groups_summary": groups_summary,
            "overall": {
                "chi2": overall_chi2,
                "df": overall_df,
                "P": overall_p,
            },
            "pairwise": pairwise_records,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_total": int(t_arr.size),
            "n_events": int((e_arr == 1).sum()),
            "n_groups": len(group_order),
            "overall_p": overall_p,
        }

        print(
            f"[logrank_test] overall chi2={overall_chi2:.4g} "
            f"df={overall_df} P={overall_p:.4g} "
            f"(n={t_arr.size}, groups={len(group_order)})"
        )
        if pairwise_records:
            print(f"  + {len(pairwise_records)} pairwise comparison(s)")

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _decode(code, encoder):
    if encoder is None:
        try:
            f = float(code)
        except (TypeError, ValueError):
            return str(code)
        if not np.isfinite(f):
            return None
        return str(int(f)) if float(f).is_integer() else str(f)
    try:
        return str(encoder.inverse[int(code)])
    except (KeyError, ValueError, TypeError):
        return None