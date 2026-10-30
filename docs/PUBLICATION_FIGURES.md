# Saved figures for publication

Studio's small scatter/table preview is a bounded inspection tool (up to 200
points). It is not a figure export. Plotting operators render the data selected
by their own parameters, independently of Studio's light/dark theme. For example,
connect PCA to **scatter**, choose `dim: component`, `x_label: PC1`, `y_label: PC2`,
and set meaningful axis labels. PCA itself produces scores and a numerical report.

After a plotting step finishes, its figures are already saved. Open **Run history
→ View results → Saved figures** and click **Open PNG**, **Open PDF** or **Open SVG**.
The same links appear beside the step's figure preview, which can also be clicked
to open the saved original. Opening a link reads the existing file; it does not
rerun the operator, change the canvas or export a screenshot.

All 14 built-in plotting operators use this output policy:

- White figure and axes background, dark labels, outward ticks, thin axes and no
  decorative UI grid or shadows. The default categorical cycle uses distinguishable
  blue/orange/green/purple colors; operator-specific scientific color mappings remain.
- PNG at 300 DPI by default, plus PDF with embedded TrueType fonts and SVG with
  editable text. Axes and text stay vector; dense point artists and heatmaps may
  be rasterized at the configured DPI. SVG text uses DejaVu Sans; install the same
  font when editing SVG elsewhere, or use the embedded-font PDF.
- The requested original format is retained. Output dimensions are not changed
  by tight bounding-box cropping. Layout reserves space inside the selected page.
- Existing files are not overwritten: repeated filenames receive a numeric suffix.

The following ordinary parameters live in each plotting operator's independent
`*.parameters.json` schema and are frozen into saved route parameter values:

| Parameter | Meaning | Default |
| --- | --- | --- |
| `figure_width_mm` | Physical output width; unspecified height follows the original aspect ratio | Operator size, capped at 180 mm wide |
| `figure_height_mm` | Explicit physical output height | Preserve aspect ratio |
| `figure_dpi` | PNG resolution and raster layers in vector formats | 300 |
| `figure_font_size` | Base text size in points; dense annotations may use operator-specific sizes | 8 |

Studio groups these controls under **Advanced parameters**. For a small panel,
start with 90 mm width and 70 mm height; set the actual dimensions and resolution
required by the destination journal. Retain enough space for long labels and
legends. Scientific axis labels, units, selected features and group definitions
still come from the operator parameters and data.

## Storage and remote runs

Figures live in the current run's `figures/` directory (under
`output/runs/<run-id>/` for managed runs). Each figure has a `.figure.json` sidecar
with its saved formats, physical size and DPI. The step report and run summary
also record the figure files, so links do not need a directory scan. Run history
resolves these records after moving a complete workspace.

Remote runs save originals on the server. Opening a link fetches only that saved
file through SSH into the verified local cache; it does not transfer the input
dataset or rerun plotting. Reconnect the server to open its files. Local browser
links need the desktop backend to remain running. An older server that lacks
format selection must be upgraded before opening newly generated companion formats.

Existing runs retain their original style and formats; opening a link never
silently rewrites historical evidence. Their original image/PDF can still be
opened from the step report, including older enrichment reports using `figure_path`.
Rerun a route to produce the new output formats. Third-party operators can expose
`figures: [{format, path, filename}]` in their step report; the files must exist
inside the job directory. The runner copies this list into the run summary. They
remain responsible for their own plotting style and complete-data semantics.

## Static plotting and R adapters

Protocol v3 now supports the public figure-artifact SDK and optional validated
`resources.r` declarations. Multiple figures retain distinct IDs across local and
SSH result viewing. See [Static plotting adapters](static_plotting.md) for the
API, dependency lifecycle, frozen JSON parameters, memory limits and examples.
