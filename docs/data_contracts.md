# Reader and operator data contracts

`Form` is the numeric tensor container. `info` describes semantics; `axis_info`
explicitly binds annotation arrays to named dimensions. Shape, field names and
array lengths alone do not establish biological meaning.

## Declaration and registry

Every built-in Reader declares `output_contract`; every Step declares ordered
`input_contracts` and `output_contract`. Dynamic outputs use `output_parameter =
"output"`. All 39 built-in operators and 13 readers publish contracts in the registry.
New external plugins use the [public protocol](operator_protocol.md) and
[SDK](sdk_quickstart.md). Existing compatibility adapters retain legacy parameter
semantics; new modules must pass protocol validation before index generation.

```python
from biopipe_sdk import MISSING, param, port

input_contracts = [port(
    dims=[param("dim")],
    info={"missing_code": MISSING,
          "ploidy": {"type": "integer", "const": 2},
          "representation": {"type": "string", "const": "hard_call"}},
    values="hard_call",
)]
output_contract = {"mode": "subset"}
```

Port rules support field types, optional fields, constants, enums, lower bounds,
array item types, dimensions, labels and axis annotations. `param()` binds a rule
to a node parameter. This small contract language is distinct from the JSON Schema
used for operator parameters.

Startup discovery generates `operators.json`, including readers and contracts.
Plugin installation updates its generation. The frontend reads this catalog; it
does not scan Python files or maintain a separate compatibility table.

## Static analysis and runtime checks

`POST /api/contracts` accepts incomplete graphs and inspects declarations and node
parameters without loading matrices or scanning available RAM:

- `compatible`: known declarations satisfy the requirements; file contents have
  not yet been validated.
- `incompatible`: known dimensions or semantic fields conflict. New wiring is
  rejected; existing conflicts are highlighted and compilation fails.
- `unknown`: labels, ploidy or output dimensions require runtime inspection.
  Wiring may be saved, but actual data must pass validation before use.

The frontend uses the same Python analyzer, debounces edits and discards stale
responses. Moving/selecting nodes does not require another semantic analysis.

Execution checks Reader output, then each Step's inputs and newly registered
outputs. A stale same-named Form cannot stand in for a fresh output. Managed cache
execution shares these rules; streaming checks metadata and actual blocks without
reloading a complete tensor just for validation. Genotype masks cover at most
65,536 values per validation block. Events record `contract_checked`; cached
artifacts preserve both `info` and `axis_info`.

HWE requires `hard_call`, diploid data and actual nonmissing values in {0,1,2}.
BGEN declares dosage and cannot connect directly to HWE. PLINK/VCF GT declare hard
calls; VCF ploidy is verified on reading and mixed ploidy fails explicitly. MAF
accepts hard calls or dosage within the allele-count range. FDR checks its P-value
column is within [0,1], allowing NaN. No automatic dosage rounding is performed.

## Metadata propagation

| Operation | Rule |
| --- | --- |
| select/drop/missing/MAF/HWE/LD pruning | Slice data, labels and bound annotations at identical positions; remove dangling encoders |
| rename_dim | Rename dimensions, label maps, axis bindings and encoder dimension references |
| transpose | Reorder tensor axes; retain annotation bindings by dimension name |
| concat | Align labels/keys first; concatenate bound annotations, filling absent values with null; reject conflicts and incompatible missing markers |
| PCA | Preserve observation annotations; remove compressed-axis annotations and genotype semantics; declare scores |
| regress | Preserve predictor annotations except response/covariates; declare regression semantics |
| FDR | Preserve annotations, pad the two new statistic columns with null, record correction_method |
| attach_info | Align by target label positions; prohibit binding one field to two axes; avoid mutating input encoders |

`Form.validate()` checks unique label positions, one-dimensional annotation arrays,
lengths, unique axis bindings and encoder references. Undeclared arrays remain
global metadata; the framework never guesses an axis.

Manually constructed genotype Forms must explicitly state `representation` as
`hard_call` or `dosage`, according to their real meaning. Ploidy alone is insufficient.
Port info popovers show declarations and inferred metadata, not whole annotation
arrays. Runtime checks remain authoritative for value-dependent requirements.

Validation: `tests/test_contracts.py`, `tests/test_sdk_agent.py`, `npm test` and
`npm run build`. Tests cover false promises, branches, cache round trips, streaming,
annotation/encoder propagation and the three compatibility states.
