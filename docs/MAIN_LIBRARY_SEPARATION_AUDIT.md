# Historical application/library separation audit

This records the pre-2.3.0 audit. The implemented boundary is documented in
[Application/library separation](application_library_boundary.md).

Inspected author `main`: `d872773243aa7212e3f1f66dd13d30a253ac638b`
(source version 2.2.2, GitHub head verified on 2026-11-04). The independent library
branch is `library/main`, inspected at `ab1ce1dd97acc2dee5a3947ebb0ab3f51ea4e7a4`.
This document records observed boundaries; it does not claim a merge to `main`.

| Layer | Current state | Remaining work |
| --- | --- | --- |
| Runtime plugin installation | v3 provider wheels/library bundles can update the installed registry independently of the EXE | Preserve this existing interface and old workflow pins |
| Release products | Studio v2.0.4 and library-v2026.11.4 are separate products | Bring the separate release workflow and version policy into main |
| Main's build configuration | `pyproject.toml` still includes `operon*` and `src*`, including all shipped Reader/operator implementations | Define separately built application and library packages, with an explicitly versioned optional offline seed |
| Library tooling | `library/release.json`, release/verification scripts, library CI and documentation exist on library/main, not inspected main | Integrate these without replacing the tested application runtime with older main engine files |
| Server bootstrap | Collects all shared bundled-provider requirements and prepares all declared model environments; source digest selects code/environment paths | Install the base service independently, then install/repair requested library capabilities from library-owned recipes |
| Resource manifests | Inspected main keeps the resource manifest under the application; library/main already packages adjacent provider resources | Make library-owned resource/environment metadata travel with the provider |
| Maintenance versioning | Author operator additions still changed the main application version | Use separate application and library versions and release checks |

The seven new external-tool adapters are already in the independent library
release. They do not justify another EXE release by themselves.

## Safe integration order

1. Fix server readiness and preserve genuine missing-capability states. Keep the
   tested desktop shutdown and cancellable precompilation changes.
2. Integrate independent library release tooling, documentation and CI into main.
3. Give application, SDK and library packages explicit ownership, build outputs
   and dependency sets. Keep the desktop's offline seed as a distribution choice,
   not an instruction to overwrite an installed library.
4. Move tool/environment install recipes into versioned library metadata. Keep
   executable availability, Python dependencies, model weights and biological
   databases distinct; a command name alone does not define an installation.
5. Verify an old desktop can install a compatible new library, two desktops can
   reuse a single server, unrelated missing tools do not block base service, and
   a workflow using a missing tool is rejected with a repairable error.

Full source/package separation and a generalized native-tool installer are outside
the scoped server-install bug fix. No wholesale main replacement or release
publication is implied by this audit.
