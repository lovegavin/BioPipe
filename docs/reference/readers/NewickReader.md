# NewickReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/newick_reader.py`](../../../src/reader/readers/newick_reader.py)
- Extensions: `.nwk, .newick, .tree`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3b.py`](../../../tests/test_extension3b.py)

## File input hints

```json
{
  "dims": [
    "node",
    "field"
  ],
  "labels": {
    "node": "builtin",
    "field": "builtin"
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
Parse a Newick tree into a node x field table.
```

### Module documentation

```text
Newick tree reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/NewickReader.md` and regenerate.
