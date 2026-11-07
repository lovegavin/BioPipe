# Independent script packages

The first verified portable target is a file-based Python script workflow with a
prepared, relocatable Python runtime. Export includes the actual runtime files,
script source, frozen parameter JSON, a readable `run.py`, platform launcher and
manifest. The independent runner imports only the standard library, never Operon
or its SDK.

```sh
operon workflow export workflow.yaml --format portable --runtime-dir ./prepared-runtime --output ./analysis-package
```

The runtime directory must contain `portable-runtime.json`:

```json
{
  "format": "operon.portable-runtime",
  "schema_version": 1,
  "platform": "win32",
  "machine": "AMD64",
  "python": "python.exe"
}
```

It must include the real interpreter, standard library, required packages, native
libraries and licenses. An arbitrary venv is rejected. Export probes the actual
interpreter, copies the runtime and probes the relocated copy; declared dependency
versions must match. It does not download packages or represent a requirements
file as a bundled environment. Target and build OS/architecture currently must
match for this verification.

Edit `INPUTS` and `OUTPUT_DIR` at the top of exported `run.py`, then run `run.cmd`
or `run.sh`. Inputs are not copied automatically. Output directories must be fresh;
existing results are preserved. Per-step logs, parameters and a run receipt are
saved beside outputs. No global PATH or system Python configuration changes occur.

Native Context/Form operators, route operators, non-Python scripts and conversions
without verified portable adapters are explicitly rejected. Scientific source
Readers also need portable adapters; export never silently omits Reader work.
The `converters/` directory is reserved for adapter implementations. Unsupported
conversion chains fail export-check rather than producing an incomplete package.
Automatic dependency solving, prebuilt environments for every platform and the
native Hi-C export adapters are not implemented by this module.

Acceptance includes a real standard-library-only Windows runtime, relocation to
a different directory, running a frozen file transformation through its bundled
interpreter and confirming Operon is not importable. This test does not establish
compatibility for every scientific dependency or Linux binary distribution.
