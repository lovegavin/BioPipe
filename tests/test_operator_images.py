"""Image declarations survive relocation, packaging and registry snapshots."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile

from PIL import Image
import pytest

from biopipe_sdk.icons import image_data, icon_path
from biopipe_sdk.protocol import describe_operator
from biopipe.dropins import single_file_wheel, snapshot_module
from biopipe.developer import embed_manifest

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="12" fill="#818cf8"/></svg>'
SOURCE = '''from biopipe_sdk import Step
class Picture(Step):
    name = "lab.picture"
    category = "analysis"
    icon = "icons/picture.svg"
    input_contracts = []
    output_contract = {"mode": "report"}
    parameters_schema = {"type": "object"}
    def run(self, ctx, inputs): pass
'''


def load_picture(path, monkeypatch):
    spec = importlib.util.spec_from_file_location("picture_example", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module.Picture


def test_image_descriptor_survives_relocation_and_source_removal(tmp_path, monkeypatch):
    (tmp_path / "icons").mkdir()
    icon = tmp_path / "icons/picture.svg"
    icon.write_bytes(SVG)
    source = tmp_path / "picture.py"
    source.write_text(SOURCE)
    cls = load_picture(source, monkeypatch)
    before = describe_operator(cls)
    assert before["icon_image"] == "data:image/svg+xml;base64," + base64.b64encode(SVG).decode()
    staged = tmp_path / "relocated"
    snapshot_module(source, staged)
    assert describe_operator(load_picture(staged / source.name, monkeypatch)) == before
    source.unlink()
    icon.unlink()
    assert base64.b64decode(json.loads(json.dumps(before))["icon_image"].split(",")[1]) == SVG


def test_only_icon_changes_invalidate_dropin_snapshot_and_wheel(tmp_path):
    source = tmp_path / "picture.py"
    source.write_text(SOURCE)
    (tmp_path / "icons").mkdir()
    icon = tmp_path / "icons/picture.svg"
    icon.write_bytes(SVG)
    first = snapshot_module(source, tmp_path / "one")
    wheel = single_file_wheel(tmp_path / "one/picture.py", tmp_path / "w1")
    with zipfile.ZipFile(wheel) as archive:
        asset = next(n for n in archive.namelist() if n.endswith("/icons/picture.svg"))
        assert archive.read(asset) == SVG
        assert asset.split("/")[0] + "/__init__.py" in archive.namelist()
    icon.write_bytes(SVG.replace(b"#818cf8", b"#34d399"))
    assert snapshot_module(source, tmp_path / "two") != first
    assert single_file_wheel(tmp_path / "two/picture.py", tmp_path / "w2").read_bytes() != wheel.read_bytes()


@pytest.mark.parametrize("extension,format,mime", [("png", "PNG", "png"), ("jpg", "JPEG", "jpeg"),
    ("jpeg", "JPEG", "jpeg"), ("webp", "WEBP", "webp"), ("gif", "GIF", "gif")])
def test_raster_formats_keep_original_bytes(tmp_path, extension, format, mime):
    path = tmp_path / ("icon." + extension)
    Image.new("RGB", (24, 24), "#818cf8").save(path, format)
    result = image_data(path)
    assert result.startswith(f"data:image/{mime};base64,")
    assert base64.b64decode(result.split(",")[1]) == path.read_bytes()
    Image.open(io.BytesIO(base64.b64decode(result.split(",")[1]))).verify()


@pytest.mark.parametrize("value", ["../other.svg", "C:/icons/a.png", "https://example.com/a.png", "/a.png", "icons/a.ico"])
def test_nonportable_paths_are_rejected(tmp_path, value):
    with pytest.raises(ValueError, match="icon"):
        icon_path(tmp_path, value)


@pytest.mark.parametrize("content", [b'<svg><script>alert(1)</script></svg>',
    b'<svg onload="alert(1)"/>', b'<svg><use href="https://example.com/a.svg"/></svg>',
    b'<svg><path fill="url(https://example.com/a.svg)"/></svg>',
    b'<!DOCTYPE svg [<!ENTITY x "a">]><svg>&x;</svg>', b'<svg><foreignObject/></svg>',
    '<!DOCTYPE svg [<!ENTITY x "a">]><svg>&x;</svg>'.encode('utf-16')])
def test_svg_rejects_active_or_external_content(tmp_path, content):
    path = tmp_path / "icon.svg"
    path.write_bytes(content)
    with pytest.raises(ValueError, match="icon SVG"):
        image_data(path)


def test_sdk_build_rejects_a_missing_packaged_icon(tmp_path):
    wheel = tmp_path / "incomplete.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("lab/__init__.py", SOURCE)
        archive.writestr("lab-1.0.0.dist-info/RECORD", "")
    descriptor = {"entry_point": "lab:Picture", "icon": "icons/picture.svg",
                  "icon_image": "data:image/svg+xml;base64," + base64.b64encode(SVG).decode()}
    with pytest.raises(ValueError, match="Missing icon in wheel"):
        embed_manifest(wheel, {"descriptors": [descriptor]})
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("lab/icons/picture.svg", SVG)
    embed_manifest(wheel, {"descriptors": [descriptor]})
    with zipfile.ZipFile(wheel) as archive:
        assert json.loads(archive.read("lab-1.0.0.dist-info/biopipe.json"))["descriptors"][0] == descriptor
