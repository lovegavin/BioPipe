"""Derived UI catalog; implementations own all executable declarations."""
from biopipe_sdk.protocol import PROTOCOL_VERSION, catalog_entry, describe_operator, describe_reader
from src.core.contracts import VERSION


def build_catalog(registry):
    from src.reader import READERS
    return {"schema_version": 1, "protocol_version": PROTOCOL_VERSION, "contract_version": VERSION,
            "operators": [catalog_entry(describe_operator(cls)) for _, cls in sorted(registry.items())],
            "readers": [catalog_entry(describe_reader(reader)) for reader in READERS]}
