"""The reference smoke route stays runnable but is not part of the example."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_reference_route_validates():
    result = subprocess.run(
        [sys.executable, "-m", "operon", "--workspace", str(ROOT), "workflow", "validate",
         "tests/fixtures/smoke_route/route.json", "--require-files"],
        cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=300,
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert '"order"' in result.stdout


def test_example_inputs_exist_without_a_route():
    assert (ROOT / "examples/smoke_real_data/input/vhh_1mel.pdb").is_file()
    assert (ROOT / "examples/smoke_real_data/input/vhh.fasta").is_file()
    assert not (ROOT / "examples/smoke_real_data/route.json").exists()
