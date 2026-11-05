# Documentation

BioPipe prepares reproducible analysis results from raw data and hands artifacts
to specialist tools for interactive interpretation and figure refinement. It
supports visual editing, human-agent collaboration and unattended execution.
BioPipe does not supply an AI model or require a desktop for computation.


## Core value

BioPipe is not a code generator. It is a contract-first analysis platform: a large,
maintainable, validated operator and Reader library lets an agent call a verified
analysis instead of writing analysis code. That avoids implementation logic errors
and the token cost of regenerating the same method. The library is the product;
visual workflows, the application API, CLI and MCP are ways to discover, compose and
trace it. See [Why BioPipe](../README.md#why-biopipe) for the five supports.

## Use BioPipe

- [End-to-end quick start](quickstart_full_flow.md)
- [Installation and dependencies](installation.md)
- [Desktop application](desktop.md)
- [Input formats and explicit Readers](input_formats.md)
- [Saved workflow parameters](workflow_parameters.md)
- [Memory, streaming and spill](resource_runtime.md)
- [Repairing the environment and provisioning resources](agent_environment_repair.md)
- [Execution environments and concurrent jobs](EXECUTION_ENVIRONMENTS.md)
- [SSH execution](REMOTE_EXECUTION.md) and [server handshake](SERVER_HANDSHAKE.md)
- [Server installation troubleshooting](SERVER_INSTALL_REPAIR.md) and [main/library separation audit](MAIN_LIBRARY_SEPARATION_AUDIT.md)
- [Hi-C workflows](HIC.md) and [16S microbiome](microbiome.md)
- [Publication figures](PUBLICATION_FIGURES.md) and [static plotting adapters](static_plotting.md)
- [Domain exports and desktop-first specialist viewers](result_viewers.md)

## Automate and integrate

- [Three-layer agent operating guide](agent_operations.md)
- [Third-party API tutorial and runnable client](api_quickstart.md)
- [Application API, headless CLI and MCP](headless_api.md)
- [Canvas collaboration and permissions](agent_api.md)
- [Operator documentation and on-demand retrieval](operator_documentation.md)
- [Operator discovery index](../library/seed/operator_index.json)
- [Reader discovery index](../library/seed/reader_index.json)
- [Application and operator-library boundary](application_library_boundary.md)

## Design notes

- [Extension policy and on-demand extension](design/extension_policy.md)
- [Hard-capability status](design/hard_capability_status.md)
- [Minibinder and VHH design route](design/minibinder_vhh_design_route.md)
- [Competitive landscape and moat analysis](design/competitive_landscape.md)
- [Agent working notes](design/agent_working_notes.md)

## Extend and maintain

- [SDK quickstart](sdk_quickstart.md) and [SDK reference](sdk_reference.md)
- [Operator protocol](operator_protocol.md) and [package protocol](package_protocol.md)
- [Reader extensions](reader_extensions.md) and [step extensions](step_extensions.md)
- [Library installation and maintenance](plugins.md)
- [Independent software and operator-library releases](library_releases.md)
- [Operator library release standard](library_release_standard.md)
- [Library 3.x full verification](verification/library-3.0.0-full.md)
- [Static registry maintenance](registry_maintenance.md)
- [Backend versioning](backend_versioning.md)
- [Selective frontend integration](FRONTEND_MERGE.md)
- [Unified main and archive](UNIFIED_MAIN.md)
- [Contributing](../CONTRIBUTING.md)

Pages under `releases/`, previous validation reports and `UPSTREAM_REVIEW_*` describe
their named historical versions. Current schemas, source declarations and CLI
help take precedence over historical counts and examples.

- [Application and library ownership, packaging and updates](application_library_boundary.md)
