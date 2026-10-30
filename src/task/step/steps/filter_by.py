# src/task/step/steps/filter_by.py
"""Filter one axis of a form using thresholds on a second form.

Two inputs share a dim (the filter dim). The first input is the data
form; the second is a metrics form whose positions along the shared
dim carry one or more statistics. The operator keeps, along the data
form's shared dim, only the positions that satisfy every rule.

Layout
------
    data     dims: [..., dim, ...]   (any ndim >= 1)
    metrics  dims: [dim, "statistic"]   (2D)
    output   dims: same as data, but dim is subset

Rules
-----
Each rule is a mapping:

    {field: <name>, min: <float>}   keep positions with value >= min
    {field: <name>, max: <float>}   keep positions with value <= max
    {field: <name>, min: <float>, max: <float>}   both

``field`` must be a label on the metrics form's ``statistic`` dim.
The metrics form's ``dim`` labels must all appear in the data form's
``dim`` labels; extra positions on either side are ignored.

Missing values
--------------
A missing value in the metrics form never satisfies a min/max rule;
the position is dropped, and the drop is recorded in the export.

Params:
    dim      : shared dim name (required)
    rules    : list of rule mappings (required, non-empty)
    output   : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._axis_contracts import estimate_axis


class FilterByStep(Step):
    """Keep positions along a dim that satisfy thresholds from another form."""
    provider = 'biopipe-core'
    parameters_file = 'filter_by.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'filter_by',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Filter by metrics',
     'description': 'Keep positions along a dim that satisfy thresholds from another form.',
     'category': '数据整理',
     'icon': 'Funnel',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}],
                               'labels': [],
                               'parallel': []},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}, 'statistic'],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'subset'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output'}



    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate_axis(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        data_form, metrics_form = inputs
        dim = ctx.step_params.get("dim")
        rules = ctx.step_params.get("rules")
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("filter_by: 'dim' is required")
        if dim not in data_form.dims:
            raise StepError(
                f"filter_by: dim '{dim}' not in data form. "
                f"Available: {data_form.dims}"
            )
        if dim not in metrics_form.dims:
            raise StepError(
                f"filter_by: dim '{dim}' not in metrics form. "
                f"Available: {metrics_form.dims}"
            )
        if not isinstance(rules, list) or not rules:
            raise StepError(
                "filter_by: 'rules' must be a non-empty list"
            )
        for r in rules:
            if not isinstance(r, dict) or "field" not in r:
                raise StepError(
                    f"filter_by: each rule must be a mapping with a "
                    f"'field' key, got {r!r}"
                )
            if "min" not in r and "max" not in r:
                raise StepError(
                    f"filter_by: rule for '{r['field']}' must have "
                    f"at least one of 'min' or 'max'"
                )

        stat_dim = [d for d in metrics_form.dims if d != dim]
        if len(stat_dim) != 1:
            raise StepError(
                f"filter_by: metrics form must be 2D with '{dim}' "
                f"plus one statistic dim, got {metrics_form.dims}"
            )
        stat_dim = stat_dim[0]
        stat_labels = metrics_form.labels.get(stat_dim, {})

        # Build a shared label list.
        data_labels = data_form.labels.get(dim, {})
        metrics_labels = metrics_form.labels.get(dim, {})
        common = [l for l in data_labels if l in metrics_labels]
        if not common:
            raise StepError(
                f"filter_by: data and metrics share no labels on "
                f"'{dim}'"
            )

        # Gather metric arrays.
        metrics_axis = metrics_form.dims.index(dim)
        stat_axis = metrics_form.dims.index(stat_dim)

        keep_mask = np.ones(len(common), dtype=bool)
        reason_per_label: dict[str, str] = {}
        for r in rules:
            field = r["field"]
            if field not in stat_labels:
                raise StepError(
                    f"filter_by: field '{field}' not in metrics "
                    f"dim '{stat_dim}'. Available: "
                    f"{sorted(stat_labels)}"
                )
            col = np.take(
                metrics_form.data,
                stat_labels[field],
                axis=stat_axis,
            )
            metric_values = np.array(
                [col[metrics_labels[l]] for l in common],
                dtype=float,
            )
            valid = np.isfinite(metric_values)

            if "min" in r:
                threshold = float(r["min"])
                pass_min = valid & (metric_values >= threshold)
                for i, ok in enumerate(pass_min):
                    if not ok and keep_mask[i]:
                        reason_per_label[common[i]] = (
                            f"{field}={metric_values[i]:.4g} < "
                            f"min {threshold}"
                            if valid[i]
                            else f"{field} is missing"
                        )
                keep_mask &= pass_min
            if "max" in r:
                threshold = float(r["max"])
                pass_max = valid & (metric_values <= threshold)
                for i, ok in enumerate(pass_max):
                    if not ok and keep_mask[i]:
                        reason_per_label[common[i]] = (
                            f"{field}={metric_values[i]:.4g} > "
                            f"max {threshold}"
                            if valid[i]
                            else f"{field} is missing"
                        )
                keep_mask &= pass_max

        n_common = len(common)
        n_kept = int(keep_mask.sum())
        if n_kept == 0:
            raise StepError(
                f"filter_by: every position along '{dim}' was "
                f"filtered out by the rules."
            )

        kept_labels = [common[i] for i in range(n_common) if keep_mask[i]]
        dropped_labels = [
            common[i] for i in range(n_common) if not keep_mask[i]
        ]

        data_axis = data_form.dims.index(dim)
        data_dim_labels = data_form.labels[dim]
        data_positions = [data_dim_labels[l] for l in kept_labels]

        new_form = data_form.subset_axis(dim, data_positions)
        ctx[out_name] = new_form

        kept_set = set(kept_labels)
        dropped_with_reason = {
            l: reason_per_label.get(l, "did not satisfy all rules")
            for l in dropped_labels
        }

        self._export_data = {
            "dim": dim,
            "stat_dim": stat_dim,
            "rules": [
                {k: v for k, v in r.items()} for r in rules
            ],
            "n_common": n_common,
            "n_before": int(data_form.data.shape[data_axis]),
            "n_after": int(new_form.data.shape[data_axis]),
            "n_removed": int(data_form.data.shape[data_axis]) - int(new_form.data.shape[data_axis]),
            "kept_labels": kept_labels,
            "dropped_labels": dropped_labels,
            "dropped_with_reason": dropped_with_reason,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "n_common": n_common,
            "n_after": int(new_form.data.shape[data_axis]),
            "n_removed": int(data_form.data.shape[data_axis]) - int(new_form.data.shape[data_axis]),
        }

        print(
            f"[filter_by] dim='{dim}' "
            f"{data_form.data.shape[data_axis]} -> "
            f"{new_form.data.shape[data_axis]} "
            f"({len(rules)} rule(s))"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
