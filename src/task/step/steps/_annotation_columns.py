"""Column-role resolution and attribute parsing for GFF3/GTF operators.

GFF3 and GTF share the same 9-column layout and record semantics,
but name the columns differently:

    role        GFF3         GTF
    ----------  -----------  -----------
    seqid       seqid        seqname
    type        type         feature
    attributes  attributes   attribute

Operators resolve their required columns by role so the same body
works on Forms produced by either reader. Attribute parsing accepts
both GTF ``key "value";`` and GFF3 ``key=value;`` syntaxes.
"""
from __future__ import annotations

import re

from src.core import StepError


ROLE_ALIASES = {
    "seqid": ("seqid", "seqname"),
    "type": ("type", "feature"),
    "attributes": ("attributes", "attribute"),
    "start": ("start",),
    "end": ("end",),
    "strand": ("strand",),
    "score": ("score",),
    "source": ("source",),
    "phase": ("phase", "frame"),
}


_GENE_ID_PATTERNS = (
    re.compile(r'\bgene_id\s*"([^"]+)"'),
    re.compile(r'\bgene_id\s*=\s*([^;]+)'),
    re.compile(r'\bID\s*=\s*([^;,]+)'),
)

_DIRECT_GENE_ID_PATTERNS = (
    re.compile(r'\bgene_id\s*"([^"]+)"'),
    re.compile(r'\bgene_id\s*=\s*([^;]+)'),
)

_RECORD_ID_PATTERNS = (
    re.compile(r'\btranscript_id\s+"([^"]+)"'),
    re.compile(r'\bID\s*=\s*([^;,]+)'),
)

_PARENT_PATTERN = re.compile(r'\bParent\s*=\s*([^;,]+)')


def require_role(labels, encoders, role, step_name, require_encoder=True):
    """Locate the column that plays ``role`` in ``labels``."""
    aliases = ROLE_ALIASES[role]
    for alias in aliases:
        if alias in labels:
            encoder = encoders.get(alias)
            if require_encoder and encoder is None:
                raise StepError(
                    f"{step_name}: '{alias}' column is not encoded"
                )
            return alias, labels[alias], encoder
    raise StepError(
        f"{step_name}: no '{role}' label found. "
        f"Tried aliases {list(aliases)}, "
        f"available columns {sorted(labels)}"
    )


def try_role(labels, encoders, role):
    """Return ``(column_name, index, encoder)`` or ``(None, None, None)``."""
    for alias in ROLE_ALIASES[role]:
        if alias in labels:
            return alias, labels[alias], encoders.get(alias)
    return None, None, None


def parse_gene_id(attributes):
    """Extract the identifier of a gene record.

    Handles GTF ``gene_id "X"``, the ``gene_id=X`` form used in some
    dialects, and GFF3 ``ID=gene:X``.
    """
    if not attributes:
        return None
    for pattern in _GENE_ID_PATTERNS:
        match = pattern.search(attributes)
        if match:
            value = match.group(1).strip()
            if ":" in value:
                value = value.split(":", 1)[1]
            return value
    return None


def parse_direct_gene_id(attributes):
    """Extract a gene id written directly on an exon or CDS record.

    Matches GTF ``gene_id "X"`` and the ``gene_id=X`` dialect. Does
    not match ``ID=gene:X``; that is the gene row's own identifier,
    extracted by ``parse_gene_id``.
    """
    if not attributes:
        return None
    for pattern in _DIRECT_GENE_ID_PATTERNS:
        match = pattern.search(attributes)
        if match:
            return match.group(1).strip()
    return None


def parse_record_id(attributes):
    """Extract a record's own identifier (transcript / mRNA / ncRNA / ...).

    Handles GTF ``transcript_id "X"`` and GFF3 ``ID=transcript:X`` or
    bare ``ID=X``. Strips a leading type prefix when present.
    """
    if not attributes:
        return None
    for pattern in _RECORD_ID_PATTERNS:
        match = pattern.search(attributes)
        if match:
            value = match.group(1).strip()
            if ":" in value:
                value = value.split(":", 1)[1]
            return value
    return None


def parse_parent(attributes):
    """Return ``(kind, id)`` for a ``Parent=`` attribute.

    ``Parent=transcript:Y_mRNA``  ->  ``("transcript", "Y_mRNA")``
    ``Parent=gene:X``             ->  ``("gene", "X")``
    ``Parent=Y``                  ->  ``("", "Y")``
    Missing                       ->  ``(None, None)``
    """
    if not attributes:
        return None, None
    match = _PARENT_PATTERN.search(attributes)
    if not match:
        return None, None
    value = match.group(1).strip()
    if ":" in value:
        kind, vid = value.split(":", 1)
        return kind, vid
    return "", value
