# MzmlReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mzml_reader.py`](../../../src/reader/readers/mzml_reader.py)
- Extensions: `.mzml`
- Compression handled natively: `False`
- Tests: [`tests/test_extension12_readers.py`](../../../tests/test_extension12_readers.py)

## File input hints

```json
{
  "dims": [
    "spectrum",
    "feature"
  ],
  "labels": {
    "spectrum": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |
| `max_spectra` | Max Spectra | integer | 100000 |  |

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
One row per mzML spectrum, with peak lists summarized.
```

### Module documentation

```text
mzML mass-spectrometry run summary reader.

The reader intentionally summarizes spectra instead of materializing peak
arrays: one row per ``<spectrum>`` with scan metadata and peak counts.  This
keeps large LC-MS runs cheap to inspect and matches the summary-oriented
contract used by the MGF reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MzmlReader.md` and regenerate.
