# docs/info_fields.py
"""Description of every field that appears in Form.info.

This file is documentation. It is not imported by any module. Its
purpose is to record what each info field means and who sets it.

Current fields
==============

    missing_code    float   set by all readers

That is the only field. Any other field is added only when an
operator needs it, at which point the operator's requirements
determine its name and meaning.

Fields not yet present
======================

    ploidy          int     will be needed by MAF, HWE
    allele_mode     str     will be needed by association
    count_units     str     will be needed by normalisation
    alphabet        str     will be needed by sequence models

These do not exist yet.
"""

# --------------------------------------------------------------------- #
# Current field
# --------------------------------------------------------------------- #

MISSING_CODE = {
    "name": "missing_code",
    "type": float,
    "meaning": (
        "Sentinel marking a missing cell in form.data. Any operator "
        "that filters, imputes, or computes statistics must compare "
        "data == missing_code."
    ),
    "set_by": {
        "vcf":     "np.nan",
        "csv":     "np.nan",
        "parquet": "np.nan",
        "plink":   "np.nan",
        "mtx":     "np.nan",
    },
    "read_by": ["describe"],
    "notes": (
        "All readers currently use nan. The field exists so a future "
        "format with a different sentinel (e.g. -1) can declare it "
        "without changing the contract."
    ),
}

# --------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------- #

RULES = """
1. A field enters Form.info only when a specific operator needs it.

2. A field whose value is derivable from form.data, form.dims, or
   form.labels does not belong in info.

3. A field whose only purpose is audit or provenance does not belong
   in info. It goes in run_metadata.json.

4. Steps that produce a new Form propagate the input's fields
   unchanged. They never add a new functional field.

5. When an operator needs a field that is not yet present, it is
   proposed here first, then added to the readers that can provide
   it, then read by the operator.
"""