# File-script branch demo

This small, synthetic workflow needs only Python's standard library. Both branches
initially multiply values by the script's imported constant, `factor = 2`.
It is an interface example, not a biological benchmark.

```sh
operon workflow lint ./workflow.yaml
operon --workspace . run ./workflow.yaml --wait --brief
```

In Studio, drag `generate.py` and `scale.py` onto a canvas. Connect the file output
to the named input. In the code tab, save/inspect the script, select `factor` and
extract it as a parameter. Its initial default is **2**, directly from the imported
source. Set one branch's value to **3**, then save the workflow. Each branch now has
its own frozen JSON values. Editing the library default later cannot replace them.

The YAML can also be prepared/exported through the CLI. To retain an extracted
schema when editing YAML by hand, use the snapshot emitted by `operon script
extract`; the original `.py` source deliberately starts with no sidecar schema.
