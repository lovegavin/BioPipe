"""Sliding-window GC and AT composition with cumulative GC skew.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna", "rna"}. The alphabet_map identifies
which numeric code stands for each of A, C, G, T; U is treated as T.

The input must contain exactly one sequence on the sequence axis.
Use select on the sequence axis first if the source has several.

For every window of window_size positions (default 10000), starting
at multiples of step_size (default = window_size):

    gc        (G + C) / valid
    at        (A + T) / valid
    gc_skew   (G - C) / (G + C)         NaN when G + C is zero
    cumulative_skew
              running (sum of G - C) / (running sum of G + C)
              accumulated across every window emitted so far, NaN
              when the running (G + C) is zero.

valid counts A, C, G, T; N and other codes are excluded. NaN padding
at the end of the sequence is excluded as well. The last window may
be shorter than window_size when the sequence length is not a
multiple of step_size.

Output:
    data   2D float32, shape (n_windows, 6)
    dims   [window, statistic]
    statistic = (start, end, gc, at, gc_skew, cumulative_skew)
    start / end are 0-based half-open positions on the sequence.
    info["window_size"], info["step_size"], info["sequence_length"],
    info["representation"] = "gc_skew_profile".

Params:
    sequence_dim : sequence axis (default "sequence")
    position_dim : position axis (default "position")
    window_size  : window length in bases (default 10000)
    step_size    : step between window starts (default window_size)
    output       : context key (default: step name)
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


_STAT_LABELS = ("start", "end", "gc", "at", "gc_skew", "cumulative_skew", "cumulative_gc")


class GcSkewProfileStep(Step):
    """GC / AT composition and cumulative GC skew over sliding windows."""

    name = "gc_skew_profile"
    category = "analysis"
    icon = "ChartLine"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sequence_dim": {"type": "string", "default": "sequence"},
            "position_dim": {"type": "string", "default": "position"},
            "window_size": {"type": "integer", "minimum": 1, "default": 10000},
            "step_size": {"type": ["integer", "null"], "minimum": 1, "default": None},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("sequence_dim", "sequence"),
              param("position_dim", "position")],
        info={
            "missing_code": MISSING,
            "representation": {"type": "string", "const": "sequence_codes"},
            "alphabet_map": {"type": "object"},
            "unknown_code": {"type": "integer"},
            "alphabet": {"type": "string", "enum": ["dna", "rna"]},
        },
    )]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        window_size = int(ctx.step_params.get("window_size", 10000))
        step_size = ctx.step_params.get("step_size")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2 or form.dims[0] != seq_dim or form.dims[1] != pos_dim:
            raise StepError(
                f"gc_skew_profile: expected 2D [{seq_dim},{pos_dim}], "
                f"got {form.dims}"
            )
        if window_size < 1:
            raise StepError(
                f"gc_skew_profile: window_size must be >= 1, got {window_size}"
            )
        if step_size is None:
            step_size = window_size
        else:
            step_size = int(step_size)
            if step_size < 1:
                raise StepError(
                    f"gc_skew_profile: step_size must be >= 1, got {step_size}"
                )

        alpha_map = form.info.get("alphabet_map")
        if not isinstance(alpha_map, dict):
            raise StepError(
                "gc_skew_profile: input is not a sequence_codes Form "
                "(info.alphabet_map missing)"
            )
        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(
                f"gc_skew_profile: requires dna/rna, got alphabet={alphabet!r}"
            )

        n_seq = int(form.data.shape[0])
        if n_seq != 1:
            raise StepError(
                f"gc_skew_profile: input must contain exactly one sequence, "
                f"got {n_seq}. Use select on '{seq_dim}' first."
            )

        code = {}
        for base in ("A", "C", "G", "T"):
            if base not in alpha_map:
                raise StepError(
                    f"gc_skew_profile: alphabet_map missing code for '{base}'"
                )
            code[base] = int(alpha_map[base])

        row = form.data[0]
        finite = np.isfinite(row)
        if not finite.any():
            raise StepError("gc_skew_profile: sequence has no finite bases")
        last = int(np.where(finite)[0].max())
        seq = row[: last + 1]
        seq_len = seq.size

        if seq_len < window_size:
            raise StepError(
                f"gc_skew_profile: sequence length {seq_len} is shorter "
                f"than window_size {window_size}"
            )

        is_a = seq == code["A"]
        is_c = seq == code["C"]
        is_g = seq == code["G"]
        is_t = seq == code["T"]

        zero = np.array([0], dtype=np.int64)
        a_cs = np.concatenate([zero, np.cumsum(is_a, dtype=np.int64)])
        c_cs = np.concatenate([zero, np.cumsum(is_c, dtype=np.int64)])
        g_cs = np.concatenate([zero, np.cumsum(is_g, dtype=np.int64)])
        t_cs = np.concatenate([zero, np.cumsum(is_t, dtype=np.int64)])

        starts = list(range(0, seq_len, step_size))

        rows: list[list[float]] = []
        run_gc = 0.0
        run_valid = 0.0
        cumulative_gc = 0.0

        for start in starts:
            end = min(start + window_size, seq_len)
            if end <= start:
                continue
            a = int(a_cs[end] - a_cs[start])
            c = int(c_cs[end] - c_cs[start])
            g = int(g_cs[end] - g_cs[start])
            t = int(t_cs[end] - t_cs[start])
            valid = a + c + g + t
            if valid == 0:
                gc = float("nan")
                at = float("nan")
            else:
                gc = (g + c) / float(valid)
                at = (a + t) / float(valid)
            if (g + c) == 0:
                gc_skew = float("nan")
            else:
                gc_skew = (g - c) / float(g + c)

            run_gc += float(g - c)
            run_valid += float(g + c)
            cumulative_gc += float(g - c)
            if run_valid == 0:
                cumulative = float("nan")
            else:
                cumulative = run_gc / run_valid

            rows.append([
                float(start), float(end), gc, at, gc_skew,
                cumulative, cumulative_gc,
            ])

        if not rows:
            raise StepError(
                "gc_skew_profile: no windows were produced; check "
                "window_size and step_size"
            )

        out_data = np.asarray(rows, dtype=np.float32)

        info, axis_info = project_metadata(form, keep_dims=[], derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "gc_skew_profile"
        info["alphabet"] = alphabet
        info["window_size"] = window_size
        info["step_size"] = step_size
        info["sequence_length"] = int(seq_len)

        window_labels = {f"w{i}": i for i in range(out_data.shape[0])}

        out_form = Form(
            data=out_data,
            dims=["window", "statistic"],
            labels={
                "window": window_labels,
                "statistic": {n: i for i, n in enumerate(_STAT_LABELS)},
            },
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        cum = out_data[:, 5]
        cum_gc = out_data[:, 6]
        finite_cum = cum[np.isfinite(cum)]
        min_cum = float(finite_cum.min()) if finite_cum.size else None
        max_cum = float(finite_cum.max()) if finite_cum.size else None
        min_idx = int(np.nanargmin(cum)) if np.isfinite(cum).any() else -1
        max_idx = int(np.nanargmax(cum)) if np.isfinite(cum).any() else -1

        min_gc_idx = int(np.argmin(cum_gc))
        max_gc_idx = int(np.argmax(cum_gc))
        min_gc = float(cum_gc[min_gc_idx])
        max_gc = float(cum_gc[max_gc_idx])

        self._export_data = {
            "sequence_dim": seq_dim,
            "position_dim": pos_dim,
            "window_size": window_size,
            "step_size": step_size,
            "sequence_length": int(seq_len),
            "n_windows": int(out_data.shape[0]),
            "min_cumulative_skew": min_cum,
            "min_cumulative_skew_window": min_idx,
            "max_cumulative_skew": max_cum,
            "max_cumulative_skew_window": max_idx,
            "min_cumulative_gc": min_gc,
            "min_cumulative_gc_window": min_gc_idx,
            "max_cumulative_gc": max_gc,
            "max_cumulative_gc_window": max_gc_idx,
        }

        print(
            f"[gc_skew_profile] length={seq_len}, window={window_size}, "
            f"step={step_size}, windows={out_data.shape[0]}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
