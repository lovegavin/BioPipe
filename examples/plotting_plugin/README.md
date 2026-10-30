# Static plotting examples

This optional package demonstrates BioPipe v3 adapters for two plotting approaches:

- `example.volcano`: Matplotlib volcano plot and adjusted-P distribution, returned
  as two independent figures, each in PDF/SVG/PNG. Input is a numeric
  `feature x stat` Form with `log2FC` and `padj` labels on the stat axis. It does not
  calculate differential expression or FDR; supply already adjusted P values.
- `example.complex_heatmap`: native R ComplexHeatmap with row/column clustering.
  Input is a numeric 2D Form. It selects the first `top_n` rows in input order,
  writes them sequentially to TSV and renders the selected matrix in R. Select
  variable genes or scientifically relevant regions upstream. Zero selects all.

Both declare full-memory operation and estimate workspace; neither promises that
clustering or rendering arbitrary matrices is streaming. Dimensions and fonts are
individual parameter JSON fields, frozen by normal workflow save/prepare.

From an environment containing this checkout of BioPipe:

```sh
python -m pip install ./examples/plotting_plugin
python examples/plotting_plugin/demo.py --output ./plotting-demo
python examples/plotting_plugin/demo.py --output ./plotting-demo-r --r
```

The demo uses synthetic matrices and writes independent `parameters.json` snapshots,
run logs and original plot files. Its `task.json` documents topology; the synthetic
input is constructed by the demo script, so that file alone is not an input bundle.
The `--r` run bootstraps R/packages if missing. Set `BIOPIPE_R_HOME` to use an isolated
acceptance directory. To distribute through Studio, build and install the manifest-bearing wheel:

```sh
biopipe plugin build ./examples/plotting_plugin
biopipe plugin install ./examples/plotting_plugin/dist/biopipe_plot_examples-0.1.0-py3-none-any.whl
```

Use the exact wheel path returned by build. You can also install it from the
operator library. Merely viewing this
example does not add optional R operators to the built-in library.

The R source is embedded in the Python implementation so code identity covers it.
Parameter JSON contains data/schema only. The package includes both parameter files.
See [the public APIs and dependency rules](../../docs/static_plotting.md).
