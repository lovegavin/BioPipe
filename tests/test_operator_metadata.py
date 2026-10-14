"""Display declarations survive SDK, catalog and generated-index boundaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from biopipe_sdk import Step
from biopipe_sdk.protocol import Descriptor, describe_operator
from src.task.operator_catalog import build_catalog


class MinimalOperator(Step):
    name = "example.metadata"
    input_contracts = []
    output_contract = {"mode": "report"}
    parameters_schema = {"type": "object", "properties": {}}

    def run(self, ctx, inputs):
        pass


def test_display_fields_are_public_optional_schema_properties():
    schema = Descriptor.model_json_schema()
    for field in ("category", "icon"):
        assert field in schema["properties"]
        assert field not in schema["required"]


def test_class_metadata_reaches_sdk_and_catalog():
    class Declared(MinimalOperator):
        category = "analysis"
        icon = "Intersect"

    for descriptor in (describe_operator(Declared), build_catalog({Declared.name: Declared})["operators"][0]):
        assert descriptor["kind"] == "operator"
        assert descriptor["category"] == "analysis"
        assert descriptor["icon"] == "Intersect"


def test_omitted_icon_preserves_existing_wheel_descriptor_shape():
    descriptor = describe_operator(MinimalOperator)
    assert descriptor["category"] == "Plugins"
    assert "icon" not in descriptor
    # Adding typed optional fields must not inject nulls into old manifests.
    assert Descriptor.model_validate(descriptor).model_dump(exclude_unset=True) == descriptor
    legacy = {"category": "Custom category", "icon": "Tag"}
    described = describe_operator(MinimalOperator, legacy)
    assert described["category"] == "Custom category"
    assert described["icon"] == "Tag"
    assert legacy == {"category": "Custom category", "icon": "Tag"}


def test_explicit_metadata_overrides_packaged_defaults_without_mutating_them():
    packaged = describe_operator(MinimalOperator)
    packaged.update(category="Plugins", icon="Tag")
    before = deepcopy(packaged)

    class Declared(MinimalOperator):
        _package_descriptor = packaged
        category = "data"
        icon = "Columns"

    described = describe_operator(Declared)
    assert described["category"] == "data"
    assert described["icon"] == "Columns"
    assert packaged == before


@pytest.mark.parametrize("field,value", [("category", ["analysis"]), ("icon", {"url": "example.svg"})])
def test_invalid_display_types_are_rejected(field, value):
    cls = type("InvalidMetadata", (MinimalOperator,), {field: value})
    with pytest.raises(ValueError, match=field):
        describe_operator(cls)


def test_new_bundled_operators_have_declared_categories_and_icons():
    from biopipe.packages import load_entry

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "biopipe/builtin_packages.json").read_text(encoding="utf-8"))
    descriptors = {d["id"]: d for p in manifest["packages"] for d in p["descriptors"]}
    expected = {"annotate": "data", "explode": "data", "order_axis": "data",
                "pivot": "data", "prioritize": "data", "enrich_go": "analysis",
                "enrichment_plot": "visualization"}
    for name, category in expected.items():
        descriptor = descriptors[name]
        cls = load_entry(descriptor)
        assert descriptor["category"] == cls.category == category
        assert descriptor["icon"] == cls.icon
        assert isinstance(cls.icon, str) and cls.icon
