"""Derived UI catalog; implementations own all executable declarations."""
from biopipe_sdk.protocol import PROTOCOL_VERSION, catalog_entry, describe_operator, describe_reader
from src.core.contracts import VERSION


def build_catalog(registry):
    from src.reader import READERS
    return {"schema_version": 1, "protocol_version": PROTOCOL_VERSION, "contract_version": VERSION,
            "operators": [catalog_entry(registry.declarations[key] if key in getattr(registry, 'declarations', {})
                                         else describe_operator(registry[key])) for key in sorted(registry)],
            "readers": [catalog_entry(describe_reader(reader)) for reader in READERS]}
