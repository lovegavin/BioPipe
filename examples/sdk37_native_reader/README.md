# SDK 3.7 native-array Reader example

Run with Operon 3.0.2/SDK 3.7 and its tested seed library:

```sh
python examples/sdk37_native_reader/demo.py --output ./native-reader-demo
```

The demonstration writes a tiny synthetic NPY, reads it as a readonly memory map,
attaches explicit dimension/label/missing-value metadata and lets the normal
Reader bridge wrap it as a Form without copying the array. It then runs the
unchanged `log_transform` operator and verifies numeric results. The bridge
does not decode arbitrary files, infer biological meaning or promise streaming
support for the downstream full-memory operator.
