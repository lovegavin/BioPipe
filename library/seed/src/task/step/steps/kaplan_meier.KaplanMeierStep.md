<!-- operon:generated -->
# KM

## Purpose

> Kaplan-Meier survival curves.
>
> Input is a single 2D form with rows = samples and columns = clinical
> variables. The operator reads three columns, groups samples by the
> group column, and draws one survival curve per group.
>
> Group values can be remapped before plotting via ``group_map``.
> This is the standard way to collapse substages (``Stage IA``,
> ``Stage IIB``) into main stages (``Stage I``, ``Stage II``), or to
> merge any set of raw labels into a smaller set of display groups.
>
> Params:
>     time_label    : column with follow-up time (required)
>     event_label   : column with event indicator (required)
>     group_label   : column with group assignment (required)
>     group_map     : optional dict {raw_value: display_value}. Raw
>                     values not in the dict are kept as-is.
>     groups        : optional list of display group names to keep,
>                     in output order
>     filename      : output file name (required)
>     title         : optional plot title
>     xlabel        : optional x-label (default "Time")
>     ylabel        : optional y-label (default "Survival probability")
>     show_censors  : mark censored observations (default True)
>     show_ci       : draw pointwise confidence bands (default False)
>     xlim          : optional [x_min, x_max]
>
> Draw Kaplan-Meier survival curves.

## Inputs and outputs

Kind: `operator`. Operator ID: `kaplan_meier`.
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

Implementation: `src/task/step/steps/kaplan_meier.py` (`KaplanMeierStep`).
