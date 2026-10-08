# src/align/align.py
"""Form-agnostic sample alignment.

Every memory form that exposes a sample dimension implements the
:class:`SampleIndexed` protocol (``sample_ids`` + ``subset_samples``).
Alignment is therefore a single, generic operation: intersect the
sample ID sets of all sample-indexed forms and reorder them to match
a reference form.

Forms that do not implement the protocol (e.g. VariantTable, which is
indexed by variant) are passed through unchanged.
"""

from __future__ import annotations

from typing import Any

from src.core.forms.protocol import SampleIndexed


def align_forms(
    forms: dict[str, Any],
    reference: str | None = None,
) -> tuple[dict[str, Any], dict]:
    """Align every sample-indexed form in ``forms`` to a common sample set.

    Parameters
    ----------
    forms : dict
        Mapping of form name to form object. Forms that do not
        implement :class:`SampleIndexed` are returned unchanged.
    reference : str, optional
        Name of the form whose sample order defines the result order.
        Defaults to the first sample-indexed form encountered in
        insertion order.

    Returns
    -------
    (aligned_forms, report)
        ``aligned_forms`` is a new dict with the same keys. Sample-indexed
        forms have been restricted to the intersection of sample IDs
        and reordered to match ``reference``. ``report`` records how
        many samples were retained and dropped per form.

    Raises
    ------
    ValueError
        If no sample-indexed form is present, or if the intersection
        of sample IDs is empty.
    """
    sample_forms = {
        name: form
        for name, form in forms.items()
        if isinstance(form, SampleIndexed)
    }

    if not sample_forms:
        raise ValueError(
            "align_forms: no sample-indexed forms found in the collection."
        )

    if reference is None:
        reference = next(iter(sample_forms))
    elif reference not in sample_forms:
        raise ValueError(
            f"align_forms: reference form '{reference}' is not "
            f"sample-indexed. Available: {sorted(sample_forms.keys())}"
        )

    # Intersect sample sets in reference order.
    ref_ids = [str(s) for s in sample_forms[reference].sample_ids]
    common = ref_ids
    for name, form in sample_forms.items():
        if name == reference:
            continue
        other = {str(s) for s in form.sample_ids}
        common = [s for s in common if s in other]

    if not common:
        raise ValueError(
            "align_forms: no common samples across sample-indexed forms. "
            f"Reference='{reference}'."
        )

    aligned: dict[str, Any] = dict(forms)
    report: dict[str, Any] = {
        "reference": reference,
        "n_common": len(common),
        "per_form": {},
    }

    for name, form in sample_forms.items():
        n_before = len(form.sample_ids)
        aligned[name] = form.subset_samples(common)
        report["per_form"][name] = {
            "n_before": int(n_before),
            "n_after": len(common),
            "n_dropped": int(n_before - len(common)),
        }

    print(
        f"[align] reference='{reference}' "
        f"common={len(common)} "
        f"forms={sorted(sample_forms.keys())}"
    )

    return aligned, report