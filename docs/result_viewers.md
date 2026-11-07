# Domain exports and specialist viewers

Operon prepares reproducible analysis artifacts, then hands them to specialist
software for interactive inspection and figure refinement. One `export_results`
operator serves every supported output format. Further computations branch from
its upstream data; exporting does not consume or replace that Form.

## Three layers

1. **Library:** format conversion lives next to `export_results`, with independent
   parameter JSON and v3 declarations. Existing native files are reused; external
   originals are copied into retained task output. No native model is reconstructed
   from insufficient summary statistics.
2. **Application:** the results panel, CLI, MCP and HTTP API share `ViewerService`.
   It matches retained file suffixes against a small declarative catalog. It never
   imports a scientific package or scans entire disks to find installed viewers.
3. **Specialist software:** the installed desktop app loads a file or the user
   opens it manually. Browser tools are secondary links. No data is automatically
   uploaded to a third-party site; no Operon credential is embedded in a URL.

A library update supplies converters but cannot add a menu to an older application.
The viewer service/UI requires the updated application. This feature does not
change protocol v3 or saved workflow parameter storage, and does not install
third-party graphical software or grant its licenses.

## User workflow

1. Add **Export results** as a branch and select a format. For a full Hi-C map,
   connect the original Cooler artifact and choose `hic`. For annotated plasmids,
   use a GenBank Reader with record retention and choose `genbank`.
2. Run the workflow. Files are already saved in that run's output folder.
3. Open the toolbar **Settings → Outputs and viewers** to set program paths and
   default desktop viewers by file extension. Expand a program row to configure
   its executable or GUI JAR. Settings also contains **Servers** and **Appearance**.
4. Open **Run history → Results**, select the exported artifact, then **Open**
   beside its file to use the saved default. The adjacent arrow offers other
   desktop apps and web alternatives; **Manage opening preferences** returns to Settings.
5. File-mode viewers receive a documented file argument. Manual-mode viewers start
   the application and shows the retained file location for its File/Open dialog.
   A successful launch response does not prove rendering or scientific validity.
6. Web entries are manual links. HiGlass, JBrowse and Vitessce may require their
   own server/reference/view configuration; opening their website is not equivalent
   to loading a local dataset. The catalog notes spell out these prerequisites.

Refresh repeats PATH/Windows App Paths discovery. Program locations are local
profile settings, never workflow fields. Use the actual EXE, or a GUI JAR plus
Java on PATH, rather than a shortcut/batch file. On macOS configure the executable
inside the `.app` bundle. A headless Linux host without a display cannot launch a
GUI; run this handoff on the desktop/client service instead.
External desktop viewers have their own lifetime: closing Operon does not close
them. Scientific workers and dependency installers retain Operon's normal cleanup.

Defaults apply only when the user requests opening a result, not automatically
after every run. The longest matching saved suffix wins (for example `.vcf.gz`
before `.gz`). Without a preference, the first available compatible desktop app
in the catalog's name ordering is used. An unavailable or removed explicit default
produces an actionable error, never a silent fallback. Clearing a preference
restores automatic selection. Preferences and executable overrides live separately
under the application profile's `viewers/` directory and survive restarts. They do
not enter workflow JSON. Route-specific execution locations, memory budgets and
parameters retain their existing independent workflow configuration.

**Remote results:** listing choices does not transfer files. Launching or obtaining
a local path uses the existing resumable output transfer/cache. Only the selected
result and retained matching index siblings are requested. This transfers those
files to the client; it is not remote range streaming. If downloaded sidecars live
in separate directories, a reusable handoff folder co-locates them using bounded
file copies. Large handoffs need local disk space. The server's original output
and computation remain there. Local retained output is opened directly; edits made
inside a specialist app should be saved under a new filename to preserve provenance.

## Conversion requirements

| Output | Required information | Limits |
| --- | --- | --- |
| HIC / Cooler | Raw integer contact counts, full chromosome sizes, fixed bin coordinates/resolution; or an original Cooler | Form must be a square symmetric window. No balanced/log/OE inversion or invented genome lengths. HIC v9, no new normalization vectors. |
| GenBank | Original annotated record strings, or axis-aligned DNA sequences and topology | Summary-only data cannot recover annotations. Sequence-only export has no invented features. |
| BED3 / bedGraph | Axis-aligned chromosome/start/end and `0-based-half-open`; bedGraph numeric value column | Optional BED fields and genome assembly are not guessed. |
| GraphML | Explicit adjacency representation and matching node labels | Undirected matrices must be symmetric; zero means no edge. |
| Newick | A complete existing tree in `info.newick` | Does not turn a distance matrix into a tree. |
| FASTA / CSV / TSV / NPY | Existing sequence/table/tensor contracts | Safe NPY excludes object arrays. |
| Other native files | An existing FileArtifact or immediate-producer native output | Reuse/copy only. No generic matrix-to-PDB/FCS/mzML/H5AD/cloupe conversion is claimed. |

See [the output operator reference](../library/seed/src/task/step/steps/export_results.ExportResultsStep.md)
for exact metadata and parameter names. Companion metadata records partial Hi-C
coverage; absent regions in an exported window are unobserved, not measured zeros.
HIC/Cooler conversion processes pixel batches and uses task-local temporary storage;
the planner estimates native buffers and genome-bin metadata. It retains the
existing memory admission, emergency spill and worker process-limit mechanisms.
GenBank record retention is full-mode metadata, not a streaming reader promise.

## Viewer catalog

This table is the implemented handoff catalog, not a claim of end-to-end validation
of every third-party installation. **File argument** means a documented launch
adapter; **manual desktop** starts the app and supplies a path. Licensing, plugins,
reference genomes and app-version compatibility remain requirements of each tool.

| Viewer | Scenario | Retained formats | Implemented handoff / reference |
| --- | --- | --- | --- |
| Juicebox | Hi-C | `.hic` | [Manual desktop](https://github.com/aidenlab/JuiceboxGUI) |
| IGV | Genome tracks | `.bam`, `.cram`, `.vcf`, `.vcf.gz`, `.bed`, `.bed.gz`, `.bedgraph`, `.bw`, `.bigwig`, `.gff`, `.gff3`, `.gtf` | [File argument](https://igv.org/doc/desktop/UserGuide/advanced/command_line/) |
| SnapGene | Plasmids | `.gb`, `.gbk`, `.gbff`, `.dna`, `.fasta`, `.fa` | [Manual desktop](https://www.snapgene.com/features/convert-file-formats) |
| UGENE | Sequences | `.gb`, `.gbk`, `.gbff`, `.fasta`, `.fa`, `.aln`, `.stockholm`, `.gff` | [Manual desktop](https://ugene.net/) |
| ApE | Plasmids | `.gb`, `.gbk`, `.fasta`, `.fa` | [Manual desktop](https://jorgensen.biology.utah.edu/wayned/ape/) |
| ChimeraX | Structures | `.pdb`, `.cif`, `.mmcif`, `.sdf`, `.mol2`, `.mrc`, `.map` | [File argument](https://www.cgl.ucsf.edu/chimerax/docs/user/options.html) |
| PyMOL | Structures | `.pdb`, `.cif`, `.mmcif`, `.sdf`, `.mol`, `.mol2`, `.ccp4` | [File argument](https://pymol.sourceforge.net/newman/user/S0200start.html) |
| Jalview | Alignments | `.fasta`, `.fa`, `.aln`, `.sto`, `.stockholm`, `.msf` | [File argument](https://www.jalview.org/help/html/features/clarguments-basic.html) |
| FigTree | Trees | `.nwk`, `.newick`, `.new`, `.tree`, `.tre`, `.nex`, `.nexus` | [Manual desktop](https://beast.community/figtree) |
| Cytoscape | Networks | `.sif`, `.gml`, `.xgmml` | [File argument](https://manual.cytoscape.org/en/latest/Command_Line_Arguments.html) |
| Gephi | Networks | `.graphml`, `.gexf`, `.gml` | [Manual desktop](https://docs.gephi.org/desktop/User_Manual/Import/) |
| Fiji / ImageJ | Microscopy | `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`, `.png`, `.jpg`, `.jpeg` | [File argument](https://imagej.net/ij/docs/guide/146-18.html) |
| napari | Microscopy | `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`, `.png`, `.jpg`, `.npy` | [File argument](https://napari.org/stable/tutorials/fundamentals/getting_started.html) |
| QuPath | Pathology | `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`, `.svs`, `.ndpi` | [File argument](https://qupath.readthedocs.io/en/stable/docs/advanced/command_line.html) |
| Bandage | Assembly graphs | `.gfa`, `.fastg` | [File argument](https://github.com/rrwick/Bandage/wiki/Command-line) |
| CELLxGENE | Single cell | `.h5ad` | [File argument](https://github.com/chanzuckerberg/cellxgene-documentation/blob/main/desktop/launch.md) |
| Loupe Browser | Single cell | `.cloupe` | [Manual desktop](https://www.10xgenomics.com/support/software/loupe-browser/latest) |
| FlowJo | Flow cytometry | `.fcs` | [Manual desktop](https://docs.flowjo.com/flowjo/workspaces-and-samples/samples-and-file-types/ws-fcsfiles/) |
| SeeMS | Mass spectrometry | `.mzml`, `.mzxml` | [Manual desktop](https://proteowizard.sourceforge.io/tools/tools_base.html) |
| Skyline | Proteomics | `.sky`, `.sky.zip` | [Manual desktop](https://skyline.ms/) |
| Mesquite | Phylogeny | `.nex`, `.nexus` | [Manual desktop](https://www.mesquiteproject.org/) |
| Juicebox Web | Hi-C | `.hic` | [Manual web / setup](https://aidenlab.github.io/juicebox-web/) |
| IGV Web | Genome tracks | `.bam`, `.cram`, `.vcf`, `.vcf.gz`, `.bed`, `.bedgraph`, `.bw`, `.bigwig`, `.gff`, `.gff3`, `.gtf` | [Manual web / setup](https://igv.org/app/) |
| JBrowse 2 | Genome tracks | `.bam`, `.cram`, `.vcf`, `.vcf.gz`, `.bed`, `.bw`, `.bigwig`, `.gff`, `.gff3`, `.gtf` | [Manual web / setup](https://jbrowse.org/code/jb2/latest/) |
| HiGlass | Hi-C | `.cool`, `.mcool` | [Manual web / setup](https://higlass.io/) |
| Mol* | Structures | `.pdb`, `.cif`, `.mmcif`, `.bcif` | [Manual web / setup](https://molstar.org/viewer/) |
| iTOL | Trees | `.nwk`, `.newick`, `.tree`, `.tre`, `.nex`, `.nexus`, `.phyloxml` | [Manual web / setup](https://itol.embl.de/) |
| PearTree | Trees | `.nwk`, `.newick`, `.tree`, `.tre`, `.nex`, `.nexus` | [Manual web / setup](https://beast.community/peartree) |
| Vitessce | Spatial / single cell | `.h5ad`, `.zarr`, `.ome.tif`, `.ome.tiff` | [Manual web / setup](https://vitessce.io/) |

Juicebox desktop releases do not all consume a file argument; the inspected
upstream GUI main entry ignores it. The default adapter therefore starts the GUI
and returns the HIC path rather than reporting a false automatic load. SnapGene's
adapter likewise uses manual opening instead of inventing a public editing API.
FigTree is retained for existing users but is deprecated upstream; PearTree is
listed as a browser alternative. IGV needs the correct assembly, BAM/CRAM/VCF
indexes as appropriate, and the CRAM reference. Operon cannot invent these files.

## CLI and MCP

First discover real job/artifact/role identifiers:

```text
operon artifacts list JOB
operon artifacts preview JOB ARTIFACT
operon artifacts viewers JOB ARTIFACT --role data
operon viewers list --refresh
operon viewers configure igv --executable "ABSOLUTE_APPLICATION_PATH"
operon viewers default .bed --viewer igv
operon artifacts open JOB ARTIFACT --role data
operon artifacts open JOB ARTIFACT --role data --viewer igv
operon artifacts prepare-viewer JOB ARTIFACT --role data
```

Omit `--executable` when configuring to clear that profile override. Omit `--viewer`
from `viewers default .bed` to clear the saved preference; omit it from `artifacts
open` to use the current default. MCP uses
`operon_viewer(job_id, artifact_id, role)` to discover choices and the same call
with `viewer="igv"` to launch. Launch needs `--allow-run`. Obtain only the required
artifact's preview; do not retrieve every operator schema or the entire matrix.
Discovery returns `default_viewer` and `default_source`; MCP discovery still never
launches anything. Pass an explicit viewer ID to launch through MCP.

## HTTP API

All routes below are on the existing loopback application API. Authenticate using
a locally discovered client with the required scopes; follow [the API tutorial](api_quickstart.md).

| Method / path | Scope | Body / result |
| --- | --- | --- |
| GET `/api/v1/viewers?refresh=true` | context | Catalog, installed/configured states and `defaults` mapping |
| POST `/api/v1/viewers/{id}/configure` | run | `{"executable":"absolute path"}` or null to reset |
| POST `/api/v1/viewers/default` | run | `{"extension":".hic","viewer":"juicebox"}`; null viewer resets |
| GET `/api/v1/jobs/{job}/artifacts/{id}/viewers?role=data` | context | Only matching choices; no output download |
| POST `/api/v1/jobs/{job}/artifacts/{id}/prepare-viewer` | run | `{"role":"data"}` → local path and index names |
| POST `/api/v1/jobs/{job}/artifacts/{id}/open-viewer` | run | `{"role":"data","viewer":"igv"}` → started, mode, path, PID and launch log |

Omit `viewer` (or pass null) on `open-viewer` to resolve the current saved default
on the server. Preference writes require execution scope, just like program-path
configuration; unprivileged clients can read compatible choices only.

```python
from operon.client import Client, data_directory

# Use the normal profile or an explicitly chosen application instance.
client = Client(data_directory(), scopes=["context", "run"])
try:
    job, artifact, role = "EXISTING_JOB", "EXISTING_ARTIFACT", "data"
    prefix = f"/v1/jobs/{job}/artifacts/{artifact}"
    choices = client.request(prefix + "/viewers?role=" + role)
    # Choose an available desktop ID from choices, not a made-up command.
    result = client.request(prefix + "/open-viewer", {"role": role, "viewer": "igv"})
    print(result["status"], result["mode"], result["path"])
finally:
    client.close()
```

The service accepts retained artifact roles, not arbitrary file paths. Executable
configuration is a separate run-authorized operation. Launch uses an argument list
with `shell=False`, never interpolated commands. Scripts, shortcuts and executable
artifact formats are not accepted as generic viewer data. App output goes to
`viewers/launch.log` under the selected application data directory. The app owns
its GUI process after launch; Operon does not kill it on exit.

## Add a viewer without adding an operator

The shipped catalog is `operon/viewers.json`. A profile can add/override entries
in `<application-data-dir>/viewers/catalog.json` using `schema_version: 1` and a
`viewers` array with the same fields. The catalog is read on demand; restart/rebuild
is unnecessary. This is trusted application configuration, not workflow data.
Use explicit extensions, `kind: desktop`, `mode: file` or `manual`, plain executable
`commands`, literal prefix `args`, supported `platforms`, `name`, `domain`, `notes`
and an official `source` URL. Web entries require a static HTTPS `url` and manual
mode. Do not put local executable paths into the shipped catalog. Configure those
per profile. Prefer a truthful manual adapter until the tool's launch contract is
verified. Do not register scripts/session formats that execute embedded code as
ordinary data.

## Verification boundary

Tests cover real synthetic HIC/Cooler count round trips, annotated GenBank
read/subset/export, genomic coordinates, network/tree semantics, native-file reuse,
index co-location, launch argument boundaries, permissions, CLI/MCP routing and
frontend interactions. Process-launch unit tests use a test double; they do not
certify third-party windows or every listed version. No commercial applications,
licenses or remote production datasets are required by these tests.
