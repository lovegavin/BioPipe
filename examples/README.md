# Protocol v2 examples

All examples target the public `biopipe_sdk` 2.0 import surface. The implementation
class is the single declaration source. There is no hand-maintained UI registry.

| Example | Demonstrates | Verification |
| --- | --- | --- |
| [dropins/scale.py](dropins/scale.py) | Single-file operator, numeric schema, metadata preservation, author SVG icon | `python -m pytest tests/test_operator_images.py tests/test_plugin_refresh.py` |
| [resource_plugin](resource_plugin/) | Stream reduction and a bounded NumPy disk Reader | `python -m biopipe plugin check examples/resource_plugin` and `python -m pytest tests/test_packages.py` |
| [Step guide](../docs/step_extensions.md) | Complete `Operator.compute` implementation and missing-value handling | `python -m pytest tests/test_extension_guides.py` |
| [Reader guide](../docs/reader_extensions.md) | Complete `Reader.read` implementation with labels | `python -m pytest tests/test_extension_guides.py` |

To start a package with tests:

```text
python -m biopipe plugin init lab_scale
python -m biopipe plugin check lab_scale
python -m biopipe plugin test lab_scale
python -m biopipe plugin build lab_scale
```

For a Reader use `--template reader`. To hot-load a single module, open Studio's
**Library Management**, use the displayed Operator/Reader directory, copy the
module and any declared icon resources there, and click **Refresh library**.
Keep dependencies in literal class declarations; compatible operators share the
host Python and conflicting ones use private dependency targets and subprocesses.

Use `parameters_schema.default` for an execution default. Only use `x-ui-default`
when the new-card suggestion should differ; this never changes an omitted runtime
parameter. Report streaming uses `flat-reduction-v1`, and disk Readers use
`dense-writer-v1`; these resource protocol names are unchanged by descriptor v2.

See the [stable protocol](../docs/operator_protocol.md),
[SDK reference](../docs/sdk_reference.md) and
[one-time migration](../docs/migration_v2.md). Existing source IDs and computation
bodies are preserved; old wheel manifests must be rebuilt under the current SDK.
