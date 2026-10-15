# Bundled pgenlib Windows extension

The Windows x64 runtime includes pgenlib 0.95.1, distributed under LGPL-3.0-only.
Its license is retained in `runtime/python/Lib/site-packages/pgenlib-0.95.1.dist-info/`.
BioPipe's release assets include the corresponding modified source archive,
`pgenlib-0.95.1-biopipe-windows-source.tar.gz`, including the build recipe and the
zlib 1.3.2 source linked into this extension. The upstream bundled libdeflate and
zstd notices are retained with those sources. The extension is a separate `.pyd`
file and can be replaced/rebuilt without rebuilding the BioPipe desktop host.

Sources:

- pgenlib: <https://pypi.org/project/pgenlib/0.95.1/> and
  <https://github.com/chrchang/plink-ng/tree/master/2.0/Python>
- zlib: <https://zlib.net/>

Verified source SHA-256 values:

```text
3807cbf34888a51bf5de60ad242d95258fc78619725c1410190e407c1c3aca20  pgenlib-0.95.1.tar.gz
bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16  zlib-1.3.2.tar.gz
```

The build uses clang-cl with the Microsoft x64 SDK and C runtime. Adaptations are
Windows compiler flags, equivalent 64-bit file-position API names, Windows I/O
headers, UTF-8 to wide-character filename conversion and an explicit cast between
the two 32-bit integer pointer spellings in the NumPy binding. Genotype algorithms
are unchanged. See
`scripts/build_pgenlib_windows.py` in the repository/source archive for rebuilding.
The native compiler itself is not distributed in the end-user ZIP.
