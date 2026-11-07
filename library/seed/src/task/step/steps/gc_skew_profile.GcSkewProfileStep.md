<!-- operon:generated -->
# gc_skew_profile

## Purpose

> Sliding-window GC and AT composition with cumulative GC skew.
>
> Input: any Form declaring info["representation"] == "sequence_codes"
> with info["alphabet"] in {"dna", "rna"}. The alphabet_map identifies
> which numeric code stands for each of A, C, G, T; U is treated as T.
>
> The input must contain exactly one sequence on the sequence axis.
> Use select on the sequence axis first if the source has several.
>
> For every window of window_size positions (default 10000), starting
> at multiples of step_size (default = window_size):
>
>     gc        (G + C) / valid
>     at        (A + T) / valid
>     gc_skew   (G - C) / (G + C)         NaN when G + C is zero
>     cumulative_skew
>               running (sum of G - C) / (running sum of G + C)
>               accumulated across every window emitted so far, NaN
>               when the running (G + C) is zero.
>     cumulative_gc
>               running sum of (G - C) across emitted windows.
>
> valid counts A, C, G, T; N and other codes are excluded. NaN padding
> at the end of the sequence is excluded as well. The last window may
> be shorter than window_size when the sequence length is not a
> multiple of step_size.
>
> Output:
>     data   2D float32, shape (n_windows, 7)
>     dims   [window, statistic]
>     statistic = (start, end, gc, at, gc_skew, cumulative_skew, cumulative_gc)
>     start / end are 0-based half-open positions on the sequence.
>     info["window_size"], info["step_size"], info["sequence_length"],
>     info["representation"] = "gc_skew_profile".
>
> Params:
>     sequence_dim : sequence axis (default "sequence")
>     position_dim : position axis (default "position")
>     window_size  : window length in bases (default 10000)
>     step_size    : step between window starts (default window_size)
>     output       : context key (default: step name)

## Inputs and outputs

Kind: `operator`. Operator ID: `gc_skew_profile`.
Input count: `1`.
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

Runs in the shared Operon interpreter.

## Limitations

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/task/step/steps/gc_skew_profile.py` (`GcSkewProfileStep`).
