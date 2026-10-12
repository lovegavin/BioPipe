# src/task/step/steps/kaplan_meier.py
"""Kaplan-Meier survival curves.

Input is a single 2D form with rows = samples and columns = clinical
variables. The operator reads three columns, groups samples by the
group column, and draws one survival curve per group.

Group values can be remapped before plotting via ``group_map``.
This is the standard way to collapse substages (``Stage IA``,
``Stage IIB``) into main stages (``Stage I``, ``Stage II``), or to
merge any set of raw labels into a smaller set of display groups.

Params:
    time_label    : column with follow-up time (required)
    event_label   : column with event indicator (required)
    group_label   : column with group assignment (required)
    group_map     : optional dict {raw_value: display_value}. Raw
                    values not in the dict are kept as-is.
    groups        : optional list of display group names to keep,
                    in output order
    filename      : output file name (required)
    title         : optional plot title
    xlabel        : optional x-label (default "Time")
    ylabel        : optional y-label (default "Survival probability")
    show_censors  : mark censored observations (default True)
    show_ci       : draw pointwise confidence bands (default False)
    xlim          : optional [x_min, x_max]
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.core.forms.metadata import project_metadata
from src.task.step.steps._plot_helpers import save_figure, setup_style


class KaplanMeierStep(Step):
    """Draw Kaplan-Meier survival curves."""

    name = "kaplan_meier"
    inputs_arity = 1
    outputs = []
    input_contracts = [{**port(ndim=2), "labels_axis": [{"axis": 1, "values": [param("time_label"), param("event_label"), param("group_label")]}]}]
    output_contract = {"mode": "none"}

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        time_label = ctx.step_params.get("time_label")
        event_label = ctx.step_params.get("event_label")
        group_label = ctx.step_params.get("group_label")
        group_map = ctx.step_params.get("group_map")
        groups_arg = ctx.step_params.get("groups")
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        xlabel = ctx.step_params.get("xlabel", "Time")
        ylabel = ctx.step_params.get(
            "ylabel", "Survival probability"
        )
        show_censors = bool(ctx.step_params.get("show_censors", True))
        show_ci = bool(ctx.step_params.get("show_ci", False))
        xlim = ctx.step_params.get("xlim")

        for name, v in (
            ("time_label", time_label),
            ("event_label", event_label),
            ("group_label", group_label),
            ("filename", filename),
        ):
            if not v:
                raise StepError(f"kaplan_meier: '{name}' is required")
        if form.data.ndim != 2:
            raise StepError(
                f"kaplan_meier: input must be 2D, got ndim={form.data.ndim}"
            )

        group_map_norm: dict[str, str] = {}
        if group_map is not None:
            if not isinstance(group_map, dict):
                raise StepError(
                    f"kaplan_meier: 'group_map' must be a dict, "
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
                    f"kaplan_meier: {name}='{lbl}' not in dim "
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

        sample_labels = form.labels[sample_dim]
        pos_to_sample = {v: k for k, v in sample_labels.items()}

        by_group: dict[str, list[tuple[float, int, str]]] = {}
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
            # Apply the user-provided remap.
            name = group_map_norm.get(name, name)
            sample = pos_to_sample.get(i, f"#{i}")
            by_group.setdefault(name, []).append(
                (float(t), int(e), sample)
            )

        if not by_group:
            raise StepError(
                "kaplan_meier: no samples with valid time, event and "
                "group values"
            )

        if groups_arg is not None:
            if not isinstance(groups_arg, list) or not groups_arg:
                raise StepError(
                    "kaplan_meier: 'groups' must be a non-empty list"
                )
            missing = [g for g in groups_arg if g not in by_group]
            if missing:
                raise StepError(
                    f"kaplan_meier: groups not found: {missing}. "
                    f"Available: {sorted(by_group)}"
                )
            group_order = list(groups_arg)
        else:
            group_order = sorted(by_group.keys())

        curves: dict[str, dict] = {}
        for g in group_order:
            samples = by_group[g]
            t_arr = np.array([s[0] for s in samples])
            e_arr = np.array([s[1] for s in samples])
            curves[g] = _km_estimate(t_arr, e_arr)

        fig, ax = plt.subplots(figsize=(5.5, 4.5))
        cmap = plt.get_cmap("tab10")

        for idx, g in enumerate(group_order):
            c = curves[g]
            color = cmap(idx % 10)
            label = f"{g} (n={c['n']})"
            ax.step(
                c["time"], c["survival"], where="post",
                color=color, lw=1.5, label=label,
            )
            if show_ci and c["ci_low"] is not None:
                ax.fill_between(
                    c["time"], c["ci_low"], c["ci_high"],
                    step="post", color=color, alpha=0.15, lw=0,
                )
            if show_censors and c["censor_times"]:
                censor_y = np.interp(
                    c["censor_times"], c["time"], c["survival"]
                )
                ax.plot(
                    c["censor_times"], censor_y, "+",
                    color=color, markersize=6, markeredgewidth=1.0,
                )

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_ylim(-0.02, 1.02)
        if xlim is not None:
            if (not isinstance(xlim, list) or len(xlim) != 2
                    or xlim[0] >= xlim[1]):
                raise StepError(
                    f"kaplan_meier: xlim must be [min, max], got {xlim}"
                )
            ax.set_xlim(xlim[0], xlim[1])
        if title:
            ax.set_title(title)
        ax.legend(frameon=False, loc="best")

        out_path = save_figure(fig, ctx, filename)

        exported_curves = {
            g: {
                "n": curves[g]["n"],
                "n_events": curves[g]["n_events"],
                "n_censored": curves[g]["n_censored"],
                "median_survival": curves[g]["median_survival"],
                "time": curves[g]["time"].tolist(),
                "survival": curves[g]["survival"].tolist(),
                "at_risk": curves[g]["at_risk"].tolist(),
                "censor_times": curves[g]["censor_times"],
            }
            for g in group_order
        }

        self._export_data = {
            "kind": "kaplan_meier",
            "filename": filename,
            "path": out_path,
            "time_label": time_label,
            "event_label": event_label,
            "group_label": group_label,
            "group_map": group_map_norm if group_map_norm else None,
            "n_samples": int(times.shape[0]),
            "groups": group_order,
            "curves": exported_curves,
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "groups": group_order,
            "n_samples": int(times.shape[0]),
            "path": out_path,
        }

        summary = " | ".join(
            f"{g}: n={curves[g]['n']}, "
            f"events={curves[g]['n_events']}, "
            f"median={_fmt(curves[g]['median_survival'])}"
            for g in group_order
        )
        print(f"[kaplan_meier] {summary} -> {out_path}")

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _km_estimate(times: np.ndarray, events: np.ndarray) -> dict:
    """Compute the Kaplan-Meier estimate for one group."""
    order = np.argsort(times)
    t = times[order]
    e = events[order]
    n_total = len(t)
    n_events = int((e == 1).sum())
    n_censored = int((e == 0).sum())

    unique_event_times = np.unique(t[e == 1])
    km_times = [0.0]
    km_surv = [1.0]
    km_at_risk = [n_total]

    s = 1.0
    for ti in unique_event_times:
        at_risk = int((t >= ti).sum())
        d_i = int(((t == ti) & (e == 1)).sum())
        s *= 1.0 - d_i / at_risk if at_risk > 0 else 1.0
        km_times.append(float(ti))
        km_surv.append(float(s))
        km_at_risk.append(at_risk)

    km_times = np.array(km_times, dtype=float)
    km_surv = np.array(km_surv, dtype=float)
    km_at_risk = np.array(km_at_risk, dtype=int)

    median = None
    below = np.where(km_surv <= 0.5)[0]
    if below.size:
        median = float(km_times[below[0]])

    censor_times = t[e == 0].tolist()

    return {
        "time": km_times,
        "survival": km_surv,
        "at_risk": km_at_risk,
        "censor_times": censor_times,
        "n": n_total,
        "n_events": n_events,
        "n_censored": n_censored,
        "median_survival": median,
        "ci_low": None,
        "ci_high": None,
    }


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


def _fmt(v):
    return "n/a" if v is None else f"{v:g}"