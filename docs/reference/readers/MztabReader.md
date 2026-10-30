# MztabReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mztab_reader.py`](../../../src/reader/readers/mztab_reader.py)
- Extensions: `.mztab`
- Compression handled natively: `False`
- Tests: [`tests/test_extension12_readers.py`](../../../tests/test_extension12_readers.py)

## File input hints

```json
{
  "dims": [
    "record",
    "feature"
  ],
  "labels": {
    "record": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |
| `section` | Section | string; enum=['auto', 'PSM', 'PEP', 'PRT', 'SML'] | auto |  |
| `max_records` | Max Records | integer | 1000000 |  |

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
One section of an mzTab file as a record x feature table.
```

### Module documentation

```text
mzTab 1.0 tab-separated proteomics/metabolomics reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MztabReader.md` and regenerate.
