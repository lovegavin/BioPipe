# BcfReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/bcf_reader.py`](../../../src/reader/readers/bcf_reader.py)
- Extensions: `.bcf`
- Compression handled natively: `False`
- Tests: [`tests/test_catalog_integrity.py`](../../../tests/test_catalog_integrity.py), [`tests/test_extension8.py`](../../../tests/test_extension8.py)

## File input hints

```json
{
  "dims": [
    "variant",
    "field"
  ],
  "labels": {
    "variant": "auto",
    "field": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `max_records` | Max Records | integer | 100000 |  |
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
BCF variant reader; exposes position, quality and allele/sample counts.
```

### Module documentation

```text
Binary VCF (BCF) variant reader using pysam.

Windows native note: pysam has no Windows wheel and pysam source builds need
a C toolchain.  Use WSL/Linux or skip BCF input on native Windows.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/BcfReader.md` and regenerate.
