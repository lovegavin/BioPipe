# Released v2.6.0 pin fixture

`v260_released_pins.json` contains only the public CsvReader/PCA implementation
identities from `Operon_Setup.exe` on the official v2.6.0 release:

- Source commit: `e539ecd3a21fa6edbb5fd5c1e424c9aa98835237`.
- Setup SHA256: `2f93df3f8f8d3e96a2c930b8565446e9606d2fc63e29fb88a765d9d9fc27ca71`.
- Policy: metadata-only bundled registry.

The extraction was checked against the release asset digest and every extracted
file's package-manifest digest. The old operators were not imported or executed.
The independent v2.6.0 RC3 acceptance export contains these same two identities.
Tests use new synthetic CSV data and a fresh profile with no historical snapshots;
this fixture contains neither user data nor a copied user profile.
