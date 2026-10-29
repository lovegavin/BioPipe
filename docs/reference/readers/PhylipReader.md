# PhylipReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/phylip_reader.py`](../../../src/reader/readers/phylip_reader.py)
- Extensions: `.phy, .phylip`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3b.py`](../../../tests/test_extension3b.py)

## File input hints

```json
{
  "dims": [
    "sequence",
    "position"
  ],
  "labels": {
    "sequence": "builtin",
    "position": "auto"
  }
}
```

## Parameters

This Reader has no parameters.

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
Reader for sequential PHYLIP alignments.
```

### Module documentation

```text
Sequential PHYLIP alignment reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/PhylipReader.md` and regenerate.
