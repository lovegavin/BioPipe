"""ProteinMPNN sequence design through the official runner script."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

_HEADER = re.compile(
    r"sample=(?P<sample>\d+),\s*score=(?P<score>-?[\d.]+),"
    r"\s*global_score=(?P<global_score>-?[\d.]+),"
    r"\s*seq_recovery=(?P<seq_recovery>-?[\d.]+)"
)
_RANGE = re.compile(r"^(?P<start>\d+)(?:-(?P<end>\d+))?$")
MODELS = ("v_48_002", "v_48_010", "v_48_020", "v_48_030")


def parse_positions(text: str) -> dict[str, list[int]]:
    """Parse ``A:97-110,A:26-33`` or ``A:1,3,5`` into chain -> positions.

    Tokens are separated by commas or whitespace.  A token containing ``:``
    starts a new chain (``A:97-110``); following bare tokens reuse the last
    chain.  Ranges are inclusive.
    """
    if not text or not str(text).strip():
        return {}
    result: dict[str, list[int]] = {}
    current_chain: str | None = None
    for token in re.split(r"[,\s]+", str(text).strip()):
        if not token:
            continue
        if ":" in token:
            chain, rest = token.split(":", 1)
            chain = chain.strip()
            if not chain or not rest:
                raise StepError(
                    f"proteinmpnn_design: '{token}' is not of the form A:97-110"
                )
            current_chain = chain
            token = rest
        if current_chain is None:
            raise StepError(
                "proteinmpnn_design: positions must start with a chain, "
                f"got '{token}'"
            )
        match = _RANGE.match(token.strip())
        if not match:
            raise StepError(
                f"proteinmpnn_design: '{token}' is not a position or range"
            )
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        if end < start:
            raise StepError(
                f"proteinmpnn_design: range '{token}' ends before it starts"
            )
        bucket = result.setdefault(current_chain, [])
        bucket.extend(range(start, end + 1))
    return {chain: sorted(set(positions)) for chain, positions in result.items()}


def pdb_chains(path: Path) -> dict[str, list[int]]:
    """Return chain -> residue numbers present in a PDB file (ATOM records)."""
    chains: dict[str, list[int]] = {}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            chain = line[21:22].strip() or "_"
            try:
                number = int(line[22:26])
            except ValueError:
                continue
            bucket = chains.setdefault(chain, [])
            if not bucket or bucket[-1] != number:
                bucket.append(number)
    if not chains:
        raise StepError(f"proteinmpnn_design: no ATOM records in '{path}'")
    return chains


def parse_design_fasta(path: Path) -> list[dict]:
    """Parse ProteinMPNN ``seqs/*.fa`` output into design records."""
    records: list[dict] = []
    header: str | None = None
    sequence: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append(_parse_header(header, "".join(sequence)))
            header = line[1:].strip()
            sequence = []
        elif header is not None:
            sequence.append(line.strip())
    if header is not None:
        records.append(_parse_header(header, "".join(sequence)))
    designs = [record for record in records if record is not None]
    if not designs:
        raise StepError(
            f"proteinmpnn_design: no generated designs found in '{path}'"
        )
    return designs


def _parse_header(header: str, sequence: str) -> dict | None:
    match = _HEADER.search(header)
    if match is None:
        return None
    return {
        "sample": int(match.group("sample")),
        "score": float(match.group("score")),
        "global_score": float(match.group("global_score")),
        "seq_recovery": float(match.group("seq_recovery")),
        "sequence": sequence,
        "header": header,
    }


class ProteinMpnnDesignStep(Step):
    """Design sequences for a PDB structure with ProteinMPNN."""

    provider = 'biopipe-core'
    parameters_file = (
        'proteinmpnn_design.ProteinMpnnDesignStep.parameters.json'
    )
    definition = {
        'protocol_version': 3,
        'id': 'proteinmpnn_design',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ProteinMPNN design',
        'description': (
            'Run the official ProteinMPNN protein_mpnn_run.py entry point on a '
            'PDB structure and return the designed sequences with their model '
            'scores.  Design ranges restrict which residues are redesigned.'
        ),
        'category': 'Machine Learning',
        'icon': 'Brain',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'mode': 'declare',
                'schema': {
                    'ndim': 2,
                    'numeric': True,
                    'info_open': True,
                    'axis_info_open': True,
                },
            },
        },
        'resources': {
            'memory_modes': ['full'],
            'supports_cuda': True,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['numpy>=1.24'],
        'dependency_imports': [],
        'inputs_arity': 0,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        structure_path = Path(str(params.get("structure_path", "")).strip()).expanduser()
        proteinmpnn_path = Path(
            str(params.get("proteinmpnn_path", "")).strip()
            or os.environ.get("BIOPIPE_PROTEINMPNN_PATH", "")
        ).expanduser()
        weights_path_text = str(params.get("weights_path", "")).strip()
        python_executable = str(params.get("python_executable", "")).strip()
        model_name = str(params.get("model_name", "v_48_020")).strip()
        num_sequences = int(params.get("num_seq_per_target", 8))
        sampling_temp = str(params.get("sampling_temp", "0.1")).strip()
        seed = int(params.get("seed", 0))
        chains = str(params.get("chains", "")).strip()
        fixed_text = str(params.get("fixed_positions", "")).strip()
        design_text = str(params.get("design_ranges", "")).strip()
        device = str(params.get("device", "cpu")).strip().lower()
        out_name = params.get("output", self.name)
        timeout = float(params.get("timeout_seconds", 1800.0))

        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_design: structure_path '{structure_path}' is not "
                "a file"
            )
        if structure_path.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "proteinmpnn_design: structure_path must be a .pdb file "
                "(ProteinMPNN needs atom names, which the PdbReader form does "
                "not carry)"
            )
        if not proteinmpnn_path.is_dir():
            raise StepError(
                f"proteinmpnn_design: proteinmpnn_path '{proteinmpnn_path}' is "
                "not a directory (set BIOPIPE_PROTEINMPNN_PATH or the "
                "proteinmpnn_path parameter)"
            )
        runner = proteinmpnn_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_design: '{runner}' does not exist; point "
                "proteinmpnn_path at the official ProteinMPNN checkout"
            )
        weights_path = Path(weights_path_text).expanduser() if weights_path_text else (
            proteinmpnn_path / "vanilla_model_weights"
        )
        weight_file = weights_path / f"{model_name}.pt"
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_design: model_name must be one of {list(MODELS)}"
            )
        if not weight_file.is_file():
            raise StepError(
                f"proteinmpnn_design: weights '{weight_file}' not found; set "
                "weights_path to the directory holding v_48_*.pt"
            )
        if num_sequences < 1:
            raise StepError(
                "proteinmpnn_design: num_seq_per_target must be at least 1"
            )
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_design: device must be 'cpu' or 'cuda'")
        if device == "cuda" and not _cuda_available():
            raise StepError(
                "proteinmpnn_design: device 'cuda' requested but CUDA is not "
                "available"
            )
        command_python = python_executable or sys.executable

        chain_residues = pdb_chains(structure_path)
        design_positions = parse_positions(design_text)
        fixed_positions = parse_positions(fixed_text)
        if design_positions and fixed_positions:
            raise StepError(
                "proteinmpnn_design: set either design_ranges or "
                "fixed_positions, not both"
            )
        if design_positions:
            for chain, positions in design_positions.items():
                known = chain_residues.get(chain)
                if known is None:
                    raise StepError(
                        f"proteinmpnn_design: design_ranges uses chain '{chain}' "
                        f"but the structure has {sorted(chain_residues)}"
                    )
                missing = [position for position in positions if position not in known]
                if missing:
                    raise StepError(
                        f"proteinmpnn_design: design_ranges positions {missing} "
                        f"are absent from chain '{chain}'"
                    )
            fixed_positions = {
                chain: [number for number in numbers if number not in set(design_positions.get(chain, ()))]
                for chain, numbers in chain_residues.items()
            }
            fixed_positions = {
                chain: numbers for chain, numbers in fixed_positions.items() if numbers
            }

        out_dir = Path(tempfile.mkdtemp(prefix="biopipe-proteinmpnn-"))
        started = time.monotonic()
        fixed_jsonl: Path | None = None
        try:
            command = [
                command_python,
                str(runner),
                "--pdb_path", str(structure_path),
                "--out_folder", str(out_dir),
                "--num_seq_per_target", str(num_sequences),
                "--sampling_temp", sampling_temp,
                "--seed", str(seed),
                "--path_to_model_weights", str(weights_path),
                "--model_name", model_name,
                "--suppress_print", "1",
            ]
            if chains:
                command.extend(["--pdb_path_chains", chains])
            if fixed_positions:
                fixed_jsonl = out_dir / "fixed_positions.jsonl"
                payload = {
                    str(structure_path): {
                        str(chain): positions
                        for chain, positions in fixed_positions.items()
                    }
                }
                fixed_jsonl.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                command.extend(["--fixed_positions_jsonl", str(fixed_jsonl)])

            environment = dict(os.environ)
            if device == "cpu":
                environment["CUDA_VISIBLE_DEVICES"] = ""
            else:
                environment.pop("CUDA_VISIBLE_DEVICES", None)

            completed = subprocess.run(
                command,
                cwd=str(proteinmpnn_path),
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()
                raise StepError(
                    "proteinmpnn_design: protein_mpnn_run.py failed with exit "
                    f"code {completed.returncode}: {tail[-800:]}"
                )
            fasta_path = out_dir / "seqs" / f"{structure_path.stem}.fa"
            if not fasta_path.is_file():
                raise StepError(
                    "proteinmpnn_design: the runner produced no "
                    f"'{fasta_path}' (stdout tail: "
                    f"{(completed.stdout or '').strip()[-400:]})"
                )
            designs = parse_design_fasta(fasta_path)
            designs.sort(key=lambda record: record["sample"])

            context_dir = _artifact_dir(ctx, "proteinmpnn")
            if context_dir is not None:
                import shutil

                shutil.copytree(out_dir, context_dir, dirs_exist_ok=True)

            data = np.array(
                [[record["score"], record["global_score"], record["seq_recovery"]]
                 for record in designs],
                dtype=np.float32,
            )
            ctx[out_name] = Form(
                data=data,
                dims=["design", "statistic"],
                labels={
                    "design": {
                        f"design_{record['sample']}": index
                        for index, record in enumerate(designs)
                    },
                    "statistic": {
                        "score": 0,
                        "global_score": 1,
                        "seq_recovery": 2,
                    },
                },
                info={
                    "missing_code": np.nan,
                    "sequences": [record["sequence"] for record in designs],
                    "headers": [record["header"] for record in designs],
                    "structure_path": str(structure_path),
                    "proteinmpnn_path": str(proteinmpnn_path),
                    "model_name": model_name,
                    "sampling_temp": sampling_temp,
                    "seed": seed,
                    "device": device,
                    "design_positions": design_positions,
                    "command": command,
                },
            )
            elapsed = time.monotonic() - started
            self._export_data = {
                "command": command,
                "model_name": model_name,
                "num_seq_per_target": num_sequences,
                "sampling_temp": sampling_temp,
                "seed": seed,
                "device": device,
                "n_designs": len(designs),
                "sequences": [record["sequence"] for record in designs],
                "scores": [record["score"] for record in designs],
                "global_scores": [record["global_score"] for record in designs],
                "seq_recovery": [record["seq_recovery"] for record in designs],
                "elapsed_seconds": round(elapsed, 3),
            }
            print(
                f"[proteinmpnn_design] {len(designs)} designs from "
                f"{structure_path.name} ({model_name}, {device}, "
                f"{elapsed:.1f}s)"
            )
        except subprocess.TimeoutExpired as exc:
            raise StepError(
                f"proteinmpnn_design: protein_mpnn_run.py timed out after "
                f"{timeout:.0f}s"
            ) from exc
        finally:
            import shutil

            shutil.rmtree(out_dir, ignore_errors=True)

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _artifact_dir(ctx: Context, name: str) -> Path | None:
    getter = getattr(ctx, "artifact_path", None)
    if getter is None:
        return None
    try:
        path = Path(getter(name))
    except Exception:
        return None
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cuda_available() -> bool:
    try:
        import torch
    except Exception:
        return False
    return bool(torch.cuda.is_available())
