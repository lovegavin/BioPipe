"""Service catalog projection. Never imports extension implementations."""
from biopipe_sdk.protocol import PROTOCOL_VERSION, catalog_entry


def catalog_from_descriptors(descriptors=()):
    return {"schema_version": 1, "protocol_version": PROTOCOL_VERSION, "contract_version": 1,
            "operators": [catalog_entry(d) for d in descriptors if d["kind"] == "operator"],
            "readers": [catalog_entry(d) for d in descriptors if d["kind"] == "reader"]}
