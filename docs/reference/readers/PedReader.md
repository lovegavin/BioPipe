# PedReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/ped_reader.py`](../../../src/reader/readers/ped_reader.py)
- Extensions: `.ped`
- Compression handled natively: `False`
- Tests: [`tests/test_extension7.py`](../../../tests/test_extension7.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "feature"
  ],
  "labels": {
    "sample": "auto",
    "feature": "builtin"
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
PLINK PED reader.
```

### Module documentation

```text
PLINK PED genotype table reader.

The six standard metadata columns are followed by two alleles per variant.
Dosage is the count of alleles different from the first allele observed for
that variant (0/1/2); fully missing genotypes become NaN.  PED does not carry
a reference allele, so this is an encoding convention, not a biological
reference.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/PedReader.md` and regenerate.
