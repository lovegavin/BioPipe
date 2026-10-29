# CytobandReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/cytoband_reader.py`](../../../src/reader/readers/cytoband_reader.py)
- Extensions: `.cytoband`
- Compression handled natively: `False`
- Tests: [`tests/test_extension4.py`](../../../tests/test_extension4.py)

## File input hints

```json
{
  "dims": [
    "region",
    "field"
  ],
  "labels": {
    "region": "auto",
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
Cytogenetic band reader.
```

### Module documentation

```text
Cytogenetic band reader.

Reads the five-column UCSC cytoband table:
chrom, start, end, band name and stain.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/CytobandReader.md` and regenerate.
