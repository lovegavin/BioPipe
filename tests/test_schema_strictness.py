"""Parameter schemas are valid and enforce their declared openness.

Existing adapters with an explicitly open parameter map remain compatible.
New extension templates default to a closed map; nested arbitrary data is not
mistaken for undeclared top-level operator options.
"""
from __future__ import annotations

from operon.packages import bundled_entries
from operon_sdk.protocol import validate_schema, validate_parameters
import pytest


def check_schema(schema):
    validate_schema(schema)
    if schema.get('additionalProperties', True) is False:
        with pytest.raises(ValueError):
            validate_parameters(schema, {'not_a_registered_parameter': True})


def test_all_reader_schemas_are_valid():
    for _, reader in bundled_entries('reader'):
        schema = reader['parameters_schema']
        check_schema(schema)


def test_all_operator_schemas_are_valid_and_protocol_v3():
    for _, spec in bundled_entries('operator'):
        check_schema(spec['parameters_schema'])
        assert spec['protocol_version'] == 3
