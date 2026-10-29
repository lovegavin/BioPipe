# NexusReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/nexus_reader.py`](../../../src/reader/readers/nexus_reader.py)
- Extensions: `.nex, .nexus`
- Compression handled natively: `False`
- Tests: [`tests/test_extension4.py`](../../../tests/test_extension4.py)

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
Reader for .nex / .nexus alignments.
```

### Module documentation

```text
NEXUS alignment reader.

Reads a simple NEXUS DATA block with a non-interleaved MATRIX. The
matrix may contain DNA or protein characters; gaps become NaN and
unknown characters use code 5.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/NexusReader.md` and regenerate.
