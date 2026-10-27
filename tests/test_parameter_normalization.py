"""YAML 1.1 numeric strings must be accepted only for declared numeric fields."""
from __future__ import annotations

import pytest

from biopipe_sdk.protocol import validate_parameters


SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "count": {"type": "integer"},
        "name": {"type": "string"},
    },
    "additionalProperties": False,
}


def test_scientific_notation_is_normalized_for_number():
    result = validate_parameters(SCHEMA, {"amount": "1e6", "name": "x"})
    assert result["amount"] == 1_000_000.0


def test_integer_string_is_normalized_only_when_integral():
    assert validate_parameters(SCHEMA, {"count": "10"})["count"] == 10
    with pytest.raises(ValueError):
        validate_parameters(SCHEMA, {"count": "10.5"})


def test_plain_string_field_is_not_coerced():
    assert validate_parameters(SCHEMA, {"name": "1e6"})["name"] == "1e6"


def test_non_numeric_string_still_fails():
    with pytest.raises(ValueError):
        validate_parameters(SCHEMA, {"amount": "not-a-number"})
