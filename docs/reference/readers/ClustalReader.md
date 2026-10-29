# ClustalReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/clustal_reader.py`](../../../src/reader/readers/clustal_reader.py)
- Extensions: `.aln, .clustal`
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
Reader for .aln / .clustal block alignments.
```

### Module documentation

```text
Clustal alignment reader.

Parses CLUSTAL/MUSCLE block alignments into a sequence x position
numeric matrix. Gaps (``-`` and ``.``) become NaN; nucleotides use the
same codes as the FASTA reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/ClustalReader.md` and regenerate.
