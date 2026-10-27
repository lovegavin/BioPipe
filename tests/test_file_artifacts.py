import json

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError, ValidationError
from src.core.contracts import describe_form, compatible, validate_form, source_schema
from src.task.context import Context
from biopipe.wire import Wire


def test_file_reference_spill_reload_and_no_payload_copy(tmp_path):
    data = tmp_path / "large.pairs"
    with data.open("wb") as out:
        out.truncate(32 * 1024 * 1024)
    ctx = Context(tmp_path / "task", {"runtime": {"memory": {"budget_mb": 1}}})
    try:
        ctx["pairs"] = FileArtifact("pairs", {"data": str(data)})
        entry = ctx.forms.entry("pairs")
        assert entry.size < 10000 and entry.external_bytes == data.stat().st_size
        ctx.forms.spill(entry, "test")
        assert entry.disk_bytes < 10000 and not (entry.disk / "data.npy").exists()
        assert ctx["pairs"].files["data"] == str(data.resolve())
        del ctx.forms["pairs"]
        assert data.is_file()  # cache eviction must not remove the original file
    finally:
        ctx.finalize()


def test_file_contract_rejects_tensor_and_keeps_existing_tensor_contracts(tmp_path):
    data = tmp_path / "a.pairs"; data.write_text("#pairs")
    artifact = FileArtifact("pairs", {"data": str(data)})
    rule = {"kind": "file", "numeric": False, "info": {"representation": {"const": "pairs"}}}
    validate_form(artifact, rule, "test")
    assert compatible(describe_form(artifact), {"numeric": True})["status"] == "incompatible"
    with pytest.raises(StepError, match="file"):
        validate_form(Form(np.ones((1,)), ["x"], {"x": {"a": 0}}), rule, "test")
    assert source_schema(rule, ["file"])["dims"] == []


def test_wire_preserves_file_identity_without_copying_data(tmp_path):
    path = tmp_path / "input.pairs"; path.write_text("input")
    wire = Wire(tmp_path)
    artifact = FileArtifact("pairs", {"data": str(path)})
    wire.write("ipc.json", artifact)
    assert wire.read("ipc.json").to_dict() == artifact.to_dict()
    assert not list(tmp_path.glob("*.npy"))
    path.write_text("changed input")
    with pytest.raises(ValidationError, match="changed"):
        wire.read("ipc.json")


def test_file_output_download_survives_workspace_move_and_rejects_external_input(tmp_path):
    from src.web.service import JobService
    old=tmp_path/'old';root=tmp_path/'moved'
    job=root/'.studio/jobs/key';data=job/'output/artifacts/map.cool'
    data.parent.mkdir(parents=True);data.write_bytes(b'synthetic')
    artifact=FileArtifact('cool',{'data':str(data)})
    payload=artifact.to_dict();payload['files']['data']=str(old/'.studio/jobs/key/output/artifacts/map.cool')
    manifest=job/'files.json';manifest.write_text(json.dumps(payload),encoding='utf-8')
    service=JobService.__new__(JobService);service.root=root;service.jobs_dir=root/'.studio/jobs'
    service.details=lambda key:{'summary':{'task_dir':str(old/'.studio/jobs/key')}}
    service.artifact=lambda key,identifier:(manifest,{'kind':'file'})
    assert service.artifact_file('key','id','data')==data
    assert service.preview('key','id')['files'][0]['downloadable']
    external=tmp_path/'input.pairs';external.write_text('external')
    manifest.write_text(json.dumps(FileArtifact('pairs',{'data':str(external)}).to_dict()),encoding='utf-8')
    assert not service.preview('key','id')['files'][0]['downloadable']
    with pytest.raises(KeyError,match='external input'):service.artifact_file('key','id','data')


def test_long_artifact_path_preview_preserves_project_boundary(tmp_path):
    from pathlib import Path
    from biopipe.bytecode import filesystem_path
    from src.web.service import JobService
    directory=tmp_path/('a'*80)/('b'*80)/('c'*80)
    native=Path(filesystem_path(directory)); native.mkdir(parents=True)
    np.save(native/'data.npy',np.arange(6).reshape(3,2))
    descriptor={'artifact_id':'pca','disk_uri':str(directory),'kind':'form'}
    service=JobService.__new__(JobService); service.root=tmp_path
    service.details=lambda key:{'report':{'artifacts':[descriptor]}}
    assert service.preview('key','pca')['points']==[[0,1],[2,3],[4,5]]
    service.root=tmp_path/'another-workspace'
    with pytest.raises(KeyError): service.artifact('key','pca')
