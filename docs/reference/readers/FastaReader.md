# FastaReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/fasta_reader.py`](../../../src/reader/readers/fasta_reader.py)
- Extensions: `.fasta, .fa, .fna, .faa`
- Compression handled natively: `False`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py)

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
    },
    "alphabet": {
      "type": "string"
    },
    "representation": {
      "type": "string",
      "const": "sequence_codes"
    },
    "alphabet_map": {
      "type": "object"
    },
    "unknown_code": {
      "type": "integer"
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
Reader for .fasta / .fa / .fna / .faa files.
```

### Module documentation

```text
FASTA reader.

Parses nucleotide or protein sequences.

Layout:
    axis 0 = sequence, axis 1 = position.

Sequences of different lengths are padded with NaN to the maximum
length found in the file. Characters are encoded as integers:

    A=0, C=1, G=2, T=3, U=3, N=4, anything else=5

Compression is handled by the framework; this reader sees plain
files only.

Label rules accepted:

    builtin           sequence: first token after '>'
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto`` for position and
``builtin`` for sequence. Duplicate identifiers are disambiguated by
appending ``#<position>``.

Sequence identifiers remain string axis labels; they are not data encoders.

The alphabet is inferred from the observed characters and recorded
in ``info["alphabet"]`` as one of ``"dna"``, ``"rna"`` or
``"protein"``.

Reference
---------
FASTA format:
https://en.wikipedia.org/wiki/FASTA_format

Info fields set:

    missing_code      np.nan
    alphabet          "dna" | "rna" | "protein"
```

## Curated notes

## 审校补充（FASTA）

- 序列按最长序列补 NaN；编码 `A=0,C=1,G=2,T/U=3,N=4,其他=5`。
- `alphabet` 由观测字符推断为 dna/rna/protein；蛋白序列不要当核酸做 GC。
- 空记录会保留为全 NaN 行；header 只取 `>` 后第一个 token 作为序列标签。
- 同一文件不能混用不同 alphabet 假设；需要分开读取或在 ANALYSIS 说明。
