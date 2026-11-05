# Localized scale

## Purpose

Multiply a numeric two-dimensional Form by `scale_factor` (default 2).
Missing values become NaN; labels and derived axis metadata are retained.
The operator declares full-memory execution and an estimate for admission planning.
It does not claim streaming support.

## Install

Copy `scale.py`, `scale.parameters.json`, `scale.i18n.json` and `scale.md` into the
operator source directory. Open the library **+**, then **Scan for operators**.
Switch Settings → Language between English and Simplified Chinese. Names and
labels change; `scale_factor`, its value, and output port identity stay unchanged.

## Parameters and outputs

The parameter JSON is the schema and default source. Saved workflows own separate
frozen value JSON. The output is a numeric Form with the input shape and labels.
This is a presentation example, not a replacement for a domain normalization method.

## Compatibility

Requires SDK 3.5. The descriptor retains protocol major 3. Removing the optional
`localization_file` declaration produces a single-language v3 operator.
