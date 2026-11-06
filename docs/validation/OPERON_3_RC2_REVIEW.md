# Operon 3.0.0 RC2 acceptance follow-up

Date: 2026-11-07. Source: the user's test-machine acceptance summary. The remote
evidence archive itself has not been independently retrieved in this session.
Reported SHA256: `5dfb62b0993d9da8e435c9f3cc58ec3fbeb4ce73a5867f099e641a4eb238616f`.
RC2 did not pass every gate and remains unpublished.

The tester reported passing the management environment, explicit preparation,
desktop Agent six phases, original PNG/PDF/SVG viewing, branched scripts, YAML,
frozen parameters, preferences, isolated reinstall and uninstall. Three backend
exits returned zero. Old-profile baselines and 262 sampled files were preserved.

The new reusable operator required manual refresh to appear. Refresh and Python
file dragging were observed to be slow or intermittently unresponsive; no timings
or incident rate were measured. The tester did not receive the forwarding guide.
The local RC2 delivery does contain that guide and lists it in its checksum file;
the exact point of transfer loss is unknown. RC3 uses one test ZIP to carry all
materials together.

The backend could not reproduce missing registration: both publish and the next
catalog read contained the saved ID. The frontend changes protect against late
catalog replies and reveal the saved ID despite an old filter/collapsed category.
OS file drags now request copy instead of move, and pending imports are visible.
These changes still require a test-machine recheck of the reported symptoms.

Profiling found repeated parsing of a roughly 3.8 MB registry on routine requests.
Metadata-only services now invalidate a catalog snapshot using file metadata,
including atomic external replacements. Source-aware development mode retains
its original checks; workers still verify execution identity. Refresh work runs
off the asynchronous request loop. Polling an unchanged generation returns a small
null response. Unchanged source refreshes hash without copying a staging tree;
changed sources still get an immutable exact-byte snapshot. Script text inspection
does not stage temporary files or execute the uploaded code.

Additional regression tests exposed two registration issues. JSON-only parameter
edits compared an unfiltered host SDK requirement against installed scientific
requirements, unnecessarily rebuilding the wheel. Both paths now use the same
normalization and still reject incompatible SDK versions. New code installations
again precompile bytecode without importing operator implementations or installing
scientific dependencies; worker startup can reuse that immutable bytecode.

Old v3/v3.5 route import, node dragging, multiselection/copy/undo, collaboration
diff expansion and SDK 3.6 conversion UI/runtime remain test-machine gates.
No Linux/Hi-C scientific validation or Python-free startup is claimed here.
