# GenBankReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/genbank_reader.py`](../../../src/reader/readers/genbank_reader.py)
- Extensions: `.gb, .gbk, .gbff`
- Compression handled natively: `False`
- Tests: [`tests/test_extension8.py`](../../../tests/test_extension8.py)

## File input hints

```json
{
  "dims": [
    "record",
    "field"
  ],
  "labels": {
    "record": "auto",
    "field": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |

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
Summary reader for GenBank (.gb/.gbk/.gbff) flat files.
```

### Module documentation

```text
GenBank flat-file summary reader.

One output row per LOCUS record.  The sequence itself is not returned;
``length``, GC fraction and the number of top-level feature keys are.
This is a dependency-free parser for the common GenBank flat-file layout.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/GenBankReader.md` and regenerate.
