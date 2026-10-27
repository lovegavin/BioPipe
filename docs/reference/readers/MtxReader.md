# MtxReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mtx_reader.py`](../../../src/reader/readers/mtx_reader.py)
- Extensions: `.mtx`
- Compression handled natively: `True`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py), [`tests/test_audit_fixes.py`](../../../tests/test_audit_fixes.py), [`tests/test_packages.py`](../../../tests/test_packages.py)

## File input hints

```json
{
  "dims": [
    "gene",
    "cell"
  ],
  "labels": {
    "gene": "builtin",
    "cell": "builtin"
  },
  "compression": [
    ".gz"
  ],
  "companions": [
    [
      "barcodes.tsv",
      "barcodes.tsv.gz"
    ],
    [
      "features.tsv",
      "features.tsv.gz",
      "genes.tsv",
      "genes.tsv.gz"
    ]
  ]
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
Reader for MatrixMarket .mtx files.
```

### Module documentation

```text
MatrixMarket MTX reader (10x Genomics MEX format).

A MEX triplet:

    matrix.mtx      sparse count matrix (gene x cell)
    barcodes.tsv    cell barcodes (columns)
    features.tsv    gene features (rows), or genes.tsv in old layouts

The three files must live in the same directory. The reader is
triggered by pointing at the .mtx file. Each of the three may be
independently gzip-compressed; compression is detected by magic
bytes, not extension.

Per the 10x Genomics documentation, each element of the matrix is
the number of UMIs associated with a feature (row) and a barcode
(column). MatrixMarket coordinate format is 1-based.

The reader declares ``handles_compression = True`` because siblings
must be read from the original directory, not from a temporary file.

Label rules accepted:

    builtin           gene: features.tsv col 0
                      cell: barcodes.tsv
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Identifiers remain string axis labels, separate from the numeric count matrix.

Reference
---------
10x Genomics MEX format:
https://support.10xgenomics.com/single-cell-gene-expression/software/pipelines/latest/output/matrices

Info fields set:

    missing_code      np.nan
```

## Curated notes

## 审校补充（MTX）

- 需要同目录的 `matrix.mtx` + `barcodes.tsv` + `features.tsv`（旧版 `genes.tsv`）。
- 三个文件可各自 gzip；压缩按 magic bytes 检测，不只看扩展名。
- 矩阵是 gene × cell 的 UMI counts；MatrixMarket 坐标 1-based。
- 只指向 `.mtx`；缺少 sibling 会报错，不会静默读空。
- 重复 gene/cell 标签会加 `#position`；下游按标签对齐时注意。
