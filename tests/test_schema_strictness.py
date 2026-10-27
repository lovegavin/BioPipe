"""Every built-in Reader/operator must reject undeclared parameters."""
from __future__ import annotations

from src.reader import READERS
from src.task import STEPS


def test_all_reader_schemas_are_strict():
    for reader in READERS:
        schema = type(reader).parameters_schema
        assert schema is not None, type(reader).__name__
        assert schema.get("additionalProperties") is False, type(reader).__name__


def test_all_operator_schemas_are_strict_and_no_legacy():
    for name, cls in STEPS.items():
        assert cls.parameters_schema is not None, name
        assert cls.parameters_schema.get("additionalProperties") is False, name
        assert not getattr(cls, "legacy_parameters", False), name
