# src/task/step/steps/permanova.py
"""PERMANOVA — permutation-based multivariate analysis of variance.

Given a distance matrix (produced by ``distance_matrix``) and a
group label for each sample, tests whether the between-group
distances are larger than expected by chance.

Two inputs share a sample dim. The first is a square distance
matrix, the second carries the group column. Both must have the
same labels on the sample dim.

Method
------
Anderson (2001) PERMANOVA on a distance matrix:

    a_ij    = d_ij^2 / 2
    SS_T    = sum over all i,j of a_ij, divided by n
    SS_W    = sum_g (1/n_g) * sum over i,j in g of a_ij
    SS_A    = SS_T - SS_W
    F       = (SS_A / (g-1)) / (SS_W / (n-g))
    R^2     = SS_A / SS_T
    p-value = fraction of permutations with F >= F_obs

Two modes
---------
    overall     one test across all groups (default)
    pairwise    one test per unordered pair of groups, in addition
                to the overall test

Output
------
    dims    = ["comparison", "statistic"]
    labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
               statistic: {"F": 0, "R2": 1, "P": 2, "n_perm": 3}}

Params:
    dist_dim        : sample dim on the distance matrix (default
                      "sample")
    group_dim       : sample dim on the metadata form (default
                      same as dist_dim)
    group_label     : column label on the metadata's other dim
                      (required)
    groups          : optional list of group names, in order; if
                      omitted, all groups present in the metadata
                      are used
    pairwise        : run pairwise tests in addition to the overall
                      test (default False)
    n_permutations  : permutation count (default 999)
    random_state    : random seed for permutations (default 0)
    output          : context key for the result (default: step name)
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import estimate


_STAT_LABELS = {"F": 0, "R2": 1, "P": 2, "n_perm": 3}


class PermanovaStep(Step):
    """PERMANOVA on a distance matrix with a grouping column."""
    provider = 'biopipe-microbiome'
    parameters_file = 'permanova.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'permanova',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'PERMANOVA',
     'description': 'PERMANOVA on a distance matrix with a grouping column.',
     'category': '统计分析',
     'icon': 'Shuffle',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dist_dim', 'default': 'sample'},
                                        {'param': 'dist_dim', 'default': 'sample', 'suffix': '_b'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'group_dim',
                                         'default': {'param': 'dist_dim', 'default': 'sample'}}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2,
                               'labels_axis': [{'axis': 1,
                                                'values': [{'param': 'group_label',
                                                            'default': None}]}]}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'dims': ['comparison', 'statistic'],
                                         'labels': {'comparison': None,
                                                    'statistic': ['F', 'R2', 'P', 'n_perm']},
                                         'axis_info': {},
                                         'info': {'missing_code': {'type': ['number', 'null']},
                                                  'representation': {'type': 'string',
                                                                     'const': 'permanova'}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output'}



    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        dist_form, meta_form = inputs
        dist_dim = ctx.step_params.get("dist_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", dist_dim)
        group_label = ctx.step_params.get("group_label")
        groups_arg = ctx.step_params.get("groups")
        pairwise = bool(ctx.step_params.get("pairwise", False))
        n_perm = int(ctx.step_params.get("n_permutations", 999))
        random_state = int(ctx.step_params.get("random_state", 0))
        out_name = ctx.step_params.get("output", self.name)

        if not group_label:
            raise StepError("permanova: 'group_label' is required")
        if n_perm < 1:
            raise StepError(
                f"permanova: n_permutations must be >= 1, "
                f"got {n_perm}"
            )
        if dist_form.data.ndim != 2:
            raise StepError(
                f"permanova: distance form must be 2D, "
                f"got ndim={dist_form.data.ndim}"
            )
        if dist_form.dims[0] != dist_dim:
            raise StepError(
                f"permanova: dist_dim '{dist_dim}' must be the first "
                f"axis of the distance form, got "
                f"{dist_form.dims}"
            )
        if dist_form.dims[1] != f"{dist_dim}_b":
            raise StepError(
                f"permanova: distance form's second axis must be "
                f"'{dist_dim}_b', got '{dist_form.dims[1]}'"
            )

        dist_labels = dist_form.labels[dist_dim]
        dist_b_labels = dist_form.labels[f"{dist_dim}_b"]

        if dist_labels != dist_b_labels:
            raise StepError(
                "permanova: distance matrix axes do not share the "
                "same label positions"
            )

        other_dims = [d for d in meta_form.dims if d != group_dim]
        if len(other_dims) != 1:
            raise StepError(
                f"permanova: metadata must be 2D with '{group_dim}' "
                f"and one other dim, got {meta_form.dims}"
            )
        other = other_dims[0]
        if group_label not in meta_form.labels.get(other, {}):
            raise StepError(
                f"permanova: group_label '{group_label}' not in dim "
                f"'{other}'. Available: "
                f"{sorted(meta_form.labels.get(other, {}))}"
            )

        meta_labels = meta_form.labels[group_dim]
        common = [s for s in dist_labels if s in meta_labels]
        if len(common) < 3:
            raise StepError(
                f"permanova: only {len(common)} common samples "
                f"between the distance matrix and the metadata"
            )

        dist_idx = [dist_labels[s] for s in common]
        meta_idx = [meta_labels[s] for s in common]

        D = dist_form.data[np.ix_(dist_idx, dist_idx)].astype(np.float64)

        group_pos = meta_form.labels[other][group_label]
        raw_codes = np.take(
            meta_form.data, meta_idx,
            axis=meta_form.dims.index(group_dim),
        )
        if raw_codes.ndim == 2:
            raw_codes = raw_codes[:, group_pos]
        else:
            raw_codes = raw_codes.ravel()
        raw_codes = np.asarray(raw_codes).ravel()
        raw_codes = np.where(raw_codes == meta_form.info.get("missing_code", np.nan), np.nan, raw_codes)

        encoders = meta_form.info.get("encoders", {})
        encoder = None
        if other in encoders and group_label in encoders[other]:
            encoder = encoders[other][group_label]

        group_names = [_decode(c, encoder) for c in raw_codes]
        valid = np.array([g is not None for g in group_names])
        if valid.sum() < 3:
            raise StepError(
                "permanova: fewer than 3 samples with a valid group "
                "value"
            )

        D = D[np.ix_(valid, valid)]
        group_names = [g for g, v in zip(group_names, valid) if v]

        all_groups = sorted(set(group_names))
        if groups_arg is not None:
            if not isinstance(groups_arg, list) or not groups_arg:
                raise StepError(
                    "permanova: 'groups' must be a non-empty list"
                )
            groups_arg = [str(g) for g in groups_arg]
            missing = [g for g in groups_arg if g not in all_groups]
            if missing:
                raise StepError(
                    f"permanova: groups not found: {missing}. "
                    f"Available: {all_groups}"
                )
            group_list = list(groups_arg)
        else:
            group_list = all_groups

        if len(group_list) < 2:
            raise StepError(
                f"permanova: need at least 2 groups, got "
                f"{len(group_list)}"
            )

        # Filter to only the requested groups BEFORE encoding.
        keep = np.array([g in group_list for g in group_names])
        D = D[np.ix_(keep, keep)]
        group_names = [g for g, k in zip(group_names, keep) if k]
        codes = np.array(
            [group_list.index(g) for g in group_names], dtype=int
        )

        n = D.shape[0]
        n_groups = len(group_list)
        if n <= n_groups:
            raise StepError(
                f"permanova: need more samples than groups, "
                f"got n={n}, groups={n_groups}"
            )

        rng = np.random.default_rng(random_state)

        rows: list[tuple[str, float, float, float, int]] = []
        overall = _permanova_core(D, codes, n_groups, n_perm, rng)
        rows.append(
            ("overall", overall["F"], overall["R2"],
             overall["P"], n_perm)
        )

        pairwise_records: list[dict] = []
        if pairwise and n_groups >= 3:
            for a, b in combinations(group_list, 2):
                ia = np.where(codes == group_list.index(a))[0]
                ib = np.where(codes == group_list.index(b))[0]
                if ia.size < 2 or ib.size < 2:
                    continue
                idx = np.concatenate([ia, ib])
                D_sub = D[np.ix_(idx, idx)]
                sub_codes = np.concatenate([
                    np.zeros(ia.size, dtype=int),
                    np.ones(ib.size, dtype=int),
                ])
                res = _permanova_core(
                    D_sub, sub_codes, 2, n_perm, rng
                )
                rows.append(
                    (f"{a} vs {b}", res["F"], res["R2"],
                     res["P"], n_perm)
                )
                pairwise_records.append({
                    "comparison": f"{a} vs {b}",
                    "F": res["F"],
                    "R2": res["R2"],
                    "P": res["P"],
                    "n_a": int(ia.size),
                    "n_b": int(ib.size),
                })

        data = np.array(
            [[r[1], r[2], r[3], float(r[4])] for r in rows],
            dtype=np.float32,
        )
        comp_labels = {r[0]: i for i, r in enumerate(rows)}

        ctx[out_name] = Form(
            data=data,
            dims=["comparison", "statistic"],
            labels={
                "comparison": comp_labels,
                "statistic": dict(_STAT_LABELS),
            },
            info={"missing_code": np.nan, "representation": "permanova"},
        )

        self._export_data = {
            "dist_dim": dist_dim,
            "group_dim": group_dim,
            "group_label": group_label,
            "groups": group_list,
            "n_samples": int(n),
            "n_permutations": n_perm,
            "overall": {
                "F": float(overall["F"]),
                "R2": float(overall["R2"]),
                "P": float(overall["P"]),
            },
            "pairwise": pairwise_records,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_samples": int(n),
            "n_groups": n_groups,
            "overall_p": float(overall["P"]),
        }

        print(
            f"[permanova] {n_groups} groups, n={n}, "
            f"F={overall['F']:.4g} R2={overall['R2']:.4g} "
            f"P={overall['P']:.4g}"
            + (f" + {len(pairwise_records)} pairwise"
               if pairwise_records else "")
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _permanova_core(D, codes, n_groups, n_perm, rng):
    """Return {F, R2, P} for one PERMANOVA test."""
    n = D.shape[0]

    def _stats(codes_now):
        a = (D ** 2) / 2.0
        SS_T = a.sum() / n
        SS_W = 0.0
        for g in range(n_groups):
            mask = codes_now == g
            n_g = int(mask.sum())
            if n_g < 2:
                continue
            sub = a[np.ix_(mask, mask)]
            SS_W += sub.sum() / n_g
        SS_A = SS_T - SS_W
        df_A = n_groups - 1
        df_W = n - n_groups
        if df_W <= 0 or SS_W <= 0:
            return None, None
        F = (SS_A / df_A) / (SS_W / df_W)
        R2 = SS_A / SS_T if SS_T > 0 else 0.0
        return F, R2

    F_obs, R2_obs = _stats(codes)
    if F_obs is None or not np.isfinite(F_obs):
        raise StepError(
            "permanova: within-group sum of squares is zero; cannot "
            "compute F"
        )

    count_ge = 0
    codes_perm = codes.copy()
    for _ in range(n_perm):
        rng.shuffle(codes_perm)
        F_p, _ = _stats(codes_perm)
        if F_p is None:
            continue
        if F_p >= F_obs - 1e-12:
            count_ge += 1

    P = (count_ge + 1) / (n_perm + 1)
    return {"F": float(F_obs), "R2": float(R2_obs), "P": float(P)}


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
