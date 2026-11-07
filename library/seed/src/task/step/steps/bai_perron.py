"""Bai-Perron multiple structural-break regression."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


def _segment_rss(y: np.ndarray, x: np.ndarray, start: int, stop: int) -> float:
    beta = np.linalg.lstsq(x[start:stop], y[start:stop], rcond=None)[0]
    resid = y[start:stop] - x[start:stop] @ beta
    return float(np.sum(resid * resid))


class BaiPerronStep(Step):
    provider = 'operon-core'
    parameters_file = 'bai_perron.BaiPerronStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bai_perron',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Bai-Perron multiple structural breaks',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Bai-Perron multiple structural breaks：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Response '
                    'Label、Predictors、N Breaks、Min Segment。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        n_breaks = int(ctx.step_params.get("n_breaks", 2))
        min_segment = float(ctx.step_params.get("min_segment", 0.15))
        out_name = ctx.step_params.get("output", self.name)

        if len(set(predictors)) != len(predictors):
            raise StepError("bai_perron: predictors must not contain duplicates")
        if not 1 <= n_breaks <= 5:
            raise StepError("bai_perron: n_breaks must lie in [1, 5]")
        if not 0.05 <= min_segment <= 0.5:
            raise StepError("bai_perron: min_segment must lie in [0.05, 0.5]")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        y = numeric_column(frame, response_label, self.name)
        keep = np.isfinite(y)
        for name in predictors:
            keep &= np.isfinite(numeric_column(frame, name, self.name))
        frame = frame.loc[keep].reset_index(drop=True)
        y = numeric_column(frame, response_label, self.name)
        x, terms = design_matrix(frame, predictors, [], self.name)
        n, k = x.shape
        min_size = max(k + 1, int(np.ceil(n * min_segment)))
        if n < (n_breaks + 1) * min_size:
            raise StepError(
                "bai_perron: not enough observations for the requested breaks "
                f"({n} rows, {n_breaks} breaks, minimum segment {min_size})"
            )

        cache: dict[tuple[int, int], float] = {}

        def rss(start: int, stop: int) -> float:
            key = (start, stop)
            if key not in cache:
                cache[key] = _segment_rss(y, x, start, stop)
            return cache[key]

        dp = np.full((n_breaks + 1, n + 1), np.inf, dtype=np.float64)
        cut = np.full((n_breaks + 1, n + 1), -1, dtype=np.int64)
        for stop in range(min_size, n + 1):
            dp[0, stop] = rss(0, stop)
        for b in range(1, n_breaks + 1):
            for stop in range((b + 1) * min_size, n + 1):
                best = np.inf
                best_start = -1
                for start in range(b * min_size, stop - min_size + 1):
                    candidate = dp[b - 1, start] + rss(start, stop)
                    if candidate < best:
                        best = candidate
                        best_start = start
                dp[b, stop] = best
                cut[b, stop] = best_start
        total_rss = float(dp[n_breaks, n])
        if not np.isfinite(total_rss) or total_rss <= 0:
            raise StepError("bai_perron: could not fit a positive-residual segmented model")

        ends: list[int] = []
        stop = n
        for b in range(n_breaks, 0, -1):
            start = int(cut[b, stop])
            if start < 0:
                raise StepError("bai_perron: no feasible breakpoint partition")
            ends.append(start)
            stop = start
        ends.reverse()
        starts = [0] + ends
        segment_ends = ends + [n]

        coefficients = []
        for start, finish in zip(starts, segment_ends):
            beta = np.linalg.lstsq(x[start:finish], y[start:finish], rcond=None)[0]
            coefficients.append(beta)
        coef_matrix = np.vstack(coefficients)

        p = (n_breaks + 1) * k + n_breaks
        bic = float(n * np.log(total_rss / n) + p * np.log(n))
        breaks = [int(value) for value in ends]
        segments = [
            {"start": int(start) + 1, "end": int(finish)}
            for start, finish in zip(starts, segment_ends)
        ]

        segment_labels = {f"segment_{i + 1}": i for i in range(n_breaks + 1)}
        term_labels = {name: i for i, name in enumerate(terms)}
        ctx[out_name] = Form(
            data=coef_matrix,
            dims=["segment", "term"],
            labels={"segment": segment_labels, "term": term_labels},
            info={
                "missing_code": np.nan,
                "method": "bai_perron",
                "breaks": breaks,
                "segments": segments,
                "rss": total_rss,
                "bic": bic,
                "n": n,
                "k": k,
                "n_breaks": n_breaks,
                "min_size": min_size,
            },
        )
        self._export = {
            "breaks": breaks,
            "segments": segments,
            "rss": total_rss,
            "bic": bic,
            "coefficients": coef_matrix.tolist(),
            "terms": terms,
            "n": n,
            "k": k,
            "n_breaks": n_breaks,
            "min_size": min_size,
        }
        print(
            f"[{self.name}] breaks={breaks}, rss={total_rss:.4g}, "
            f"bic={bic:.4g}, n={n}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
