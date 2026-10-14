"""Plugin scaffolding, source validation and wheel builds."""
import importlib
from contextlib import redirect_stdout
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import zipfile

from biopipe.plugins import run_process
from biopipe import __version__
from biopipe_sdk.protocol import describe_operator, describe_reader, validate_extension


def scaffold(path, template="operator"):
    path = Path(path).resolve()
    if path.exists() and any(path.iterdir()):
        raise ValueError("Choose a new or empty plugin directory")
    module = re.sub(r"[^a-z0-9_]", "_", path.name.lower())
    if not module or module[0].isdigit():
        module = "plugin_" + module
    package = module.replace("_", "-")
    path.mkdir(parents=True, exist_ok=True)
    (path / module).mkdir(exist_ok=True)
    reader = template == "reader"
    cls, group = ("ArrayReader", "readers") if reader else ("Scale", "operators")
    (path / "pyproject.toml").write_text(f'''[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "{package}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["biopipe-studio>={__version__},<{int(__version__.split('.')[0]) + 1}"]

[project.entry-points."biopipe.{group}"]
{module} = "{module}:{cls}"

[tool.setuptools.packages.find]
include = ["{module}*"]
''', encoding="utf-8")
    source = f'''"""Example plugin: change the calculation, parameters and contracts."""
import numpy as np
from biopipe_sdk import Operator, Form, port, project_metadata


class Scale(Operator):
    """Multiply a numeric matrix by a constant."""
    name = "example.{module}"
    version = "0.1.0"
    title = "Scale matrix"
    category = "data"
    icon = "SlidersHorizontal"  # Optional; omit for Studio's default icon.
    input_contracts = [port(ndim=2)]
    output_contract = {{"mode": "transform", "representation": "scaled"}}
    parameters_schema = {{
        "type": "object", "additionalProperties": False,
        "properties": {{"factor": {{"type": "number", "default": 2.0, "title": "Scale factor"}}}}
    }}

    def compute(self, inputs, params, context):
        form = inputs[0]
        info, axes = project_metadata(form, derived=True)
        info.update(representation="scaled", missing_code=float("nan"))
        data = form.data.astype(float, copy=True)
        missing = form.info.get("missing_code")
        if missing is not None:
            data[data == missing] = np.nan
        data *= params["factor"]
        return Form(data=data, dims=list(form.dims),
                    labels={{d: dict(v) for d, v in form.labels.items()}}, info=info, axis_info=axes)

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        cells = inputs[0].data.size
        return cells, cells * 8 + sum(len(v) for v in inputs[0].labels.values()) * 96
'''
    if reader:
        source = f'''"""Example reader for NumPy .npy arrays, with explicit dimensions."""
import numpy as np
from biopipe_sdk import Reader, Form, reader_contract


class ArrayReader(Reader):
    name = "example.{module}"
    version = "0.1.0"
    extensions = [".npy"]
    output_contract = reader_contract()
    parameters_schema = {{"type": "object", "properties": {{}}, "additionalProperties": False}}

    def read(self, path, dims, labels, **args):
        data = np.load(path, allow_pickle=False)
        if data.ndim != 2 or len(dims) != 2:
            raise ValueError("Expected a two-dimensional array and two dimension names")
        mapping = {{}}
        for d, size in zip(dims, data.shape):
            spec = labels.get(d, "auto")
            if spec == "auto":
                mapping[d] = {{str(i): i for i in range(size)}}
            elif isinstance(spec, dict) and all(isinstance(k, str) and type(v) is int for k, v in spec.items()):
                mapping[d] = dict(spec)
            else:
                raise ValueError("This reader supports auto labels or explicit name-to-position mappings")
        return Form(data=data, dims=dims, labels=mapping, info={{"missing_code": float("nan")}})
'''
    (path / module / "__init__.py").write_text(source, encoding="utf-8")
    (path / "README.md").write_text(f"# {package}\n\nGenerated BioPipe SDK v1 {template} plugin.\n\n"
        "1. Edit the implementation and contracts.\n2. Run `biopipe plugin check .`.\n"
        "3. Run `biopipe plugin test .`.\n4. Run `biopipe plugin build .`.\n"
        "5. Install the resulting wheel with `biopipe plugin install dist/<file>.whl`.\n", encoding="utf-8")
    (path / "tests").mkdir(exist_ok=True)
    if reader:
        test = f'''import numpy as np
from {module} import ArrayReader

def test_array_reader(tmp_path):
    path = tmp_path / "matrix.npy"
    np.save(path, np.arange(6).reshape(2, 3))
    form = ArrayReader().read(path, ["sample", "feature"], {{}})
    form.validate()
    assert form.data.shape == (2, 3)
'''
    else:
        test = f'''import numpy as np
from biopipe_sdk import Form
from biopipe_sdk.testing import run_operator
from {module} import Scale

def test_scale():
    data = np.arange(6, dtype=float).reshape(2, 3)
    form = Form(data=data, dims=["sample", "feature"],
                labels={{"sample": {{"a": 0, "b": 1}}, "feature": {{"x": 0, "y": 1, "z": 2}}}},
                info={{"missing_code": float("nan")}})
    output = run_operator(Scale, [form], {{"factor": 3}})
    np.testing.assert_allclose(output.data, data * 3)
    assert output.info["representation"] == "scaled"
    np.testing.assert_allclose(form.data, data)
'''
    (path / "tests/test_plugin.py").write_text(test, encoding="utf-8")
    return {"path": str(path), "module": module, "template": template}


def check_source(path):
    path = Path(path).resolve()
    # Validation imports trusted developer code in this short-lived process.
    sys.path.insert(0, str(path / "src" if (path / "src").is_dir() else path))
    project = tomllib.loads((path / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    descriptors = []
    for group, kind in (("biopipe.operators", "operator"), ("biopipe.readers", "reader")):
        for entry in project.get("entry-points", {}).get(group, {}).values():
            module, attribute = entry.split(":", 1)
            cls = getattr(importlib.import_module(module), attribute)
            validate_extension(cls, kind)
            if not cls.output_contract or (kind == "operator" and cls.input_contracts is None):
                raise ValueError(f"Missing contracts: {entry}")
            descriptor = describe_operator(cls) if kind == "operator" else describe_reader(cls())
            from biopipe.packages import owns_legacy_id
            from packaging.utils import canonicalize_name
            if "." not in descriptor["id"] and not owns_legacy_id(canonicalize_name(project["name"]), descriptor["id"]):
                raise ValueError("Use a namespaced ID such as lab.scale")
            descriptors.append(descriptor)
    if not descriptors:
        raise ValueError("No BioPipe entry points declared")
    from biopipe_sdk.protocol import PackageDescriptor
    value = {"protocol_version": 1, "name": canonicalize_name(project["name"]),
             "package": project["name"], "version": project["version"], "origin": "wheel",
             "dependencies": project.get("dependencies", []), "descriptors": descriptors}
    PackageDescriptor.model_validate(value)
    return value


def build(path):
    path = Path(path).resolve()
    previous = {p: p.stat().st_mtime_ns for p in (path / "dist").glob("*.whl")}
    manifest = json.loads(run_process([sys.executable, "-m", "biopipe.developer", "check", path]))
    run_process([sys.executable, "-m", "build", "--wheel", "--no-isolation", path], timeout=180)
    wheels = [p for p in sorted((path / "dist").glob("*.whl")) if p.stat().st_mtime_ns != previous.get(p)]
    for wheel in wheels:
        embed_manifest(wheel, manifest)
    (path / "biopipe-plugin.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"wheels": list(map(str, wheels)), "manifest": str(path / "biopipe-plugin.json")}


def embed_manifest(wheel, manifest):
    """Publish metadata inside the wheel, updating its standard RECORD hashes."""
    with zipfile.ZipFile(wheel) as archive:
        entries = {item.filename: (item, archive.read(item)) for item in archive.infolist()}
    record = next(name for name in entries if name.endswith(".dist-info/RECORD"))
    target = record.rsplit("/", 1)[0] + "/biopipe.json"
    data = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    rows = [row for row in csv.reader(io.StringIO(entries[record][1].decode("utf-8"))) if row[0] not in (target, record)]
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    rows.extend([[target, "sha256=" + digest, str(len(data))], [record, "", ""]])
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    temporary = wheel.with_suffix(".whl.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, (info, content) in entries.items():
            if name not in (record, target):
                archive.writestr(info, content)
        archive.writestr(target, data)
        archive.writestr(record, output.getvalue().encode("utf-8"))
    temporary.replace(wheel)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "check":
        with redirect_stdout(sys.stderr):
            result = check_source(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
