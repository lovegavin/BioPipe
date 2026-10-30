# Ab1Reader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/ab1_reader.py`](../../../src/reader/readers/ab1_reader.py)
- Extensions: `.ab1`
- Compression handled natively: `False`
- Tests: [`tests/test_extension15_readers.py`](../../../tests/test_extension15_readers.py), [`tests/test_r_oracles7.py`](../../../tests/test_r_oracles7.py)

## File input hints

```json
{
  "dims": [
    "base",
    "feature"
  ],
  "labels": {
    "base": "builtin",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `max_bases` | Max Bases | integer | 1000000 |  |

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
Reader for ABI .ab1 Sanger trace files.
```

### Module documentation

```text
ABIF/AB1 Sanger chromatogram reader.

ABIF files are a directory of typed tags.  The reader keeps the primary
base calls, quality values and peak positions, and adds the four raw
trace values sampled at each called peak.  The full sequence is also
stored in ``info['sequence']`` so no information is lost when the table
is passed to numeric operators.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/Ab1Reader.md` and regenerate.
