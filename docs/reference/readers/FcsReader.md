# FcsReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/fcs_reader.py`](../../../src/reader/readers/fcs_reader.py)
- Extensions: `.fcs`
- Compression handled natively: `False`
- Tests: [`tests/test_extension15_readers.py`](../../../tests/test_extension15_readers.py), [`tests/test_r_oracles7.py`](../../../tests/test_r_oracles7.py)

## File input hints

```json
{
  "dims": [
    "event",
    "channel"
  ],
  "labels": {
    "event": "auto",
    "channel": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `max_events` | Max Events | integer | 1000000 |  |

## Output contract

```json
{
  "version": 1,
  "numeric": true,
  "info": {
    "missing_code": {
      "type": [
        "number",
        "null"
      ]
    },
    "encoders": {
      "type": "object",
      "optional": true
    }
  },
  "dims": [],
  "labels": [],
  "parallel": [],
  "ndim": 2,
  "axis_fields": [],
  "info_open": false
}
```

## Processing rules (source docstring)

```text
Reader for .fcs flow-cytometry files.
```

### Module documentation

```text
FCS (Flow Cytometry Standard) reader.

The reader supports the list-mode integer/float/double FCS 2.0-3.1
layouts used by flowCore.  It exposes one row per event and one column
per parameter; parameter names come from ``$PnS``/``$PnN`` and event
labels are stable ``event:<n>`` strings.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/FcsReader.md` and regenerate.
