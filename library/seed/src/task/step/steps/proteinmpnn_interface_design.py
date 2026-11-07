"""Interface-focused ProteinMPNN design with chain, bias and tie controls."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from .proteinmpnn_design import (
    MODELS,
    parse_design_fasta,
    parse_positions,
    pdb_chains,
)

STATISTICS = ("score", "global_score", "seq_recovery")
_AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"


def parse_bias(text: str) -> dict[str, float]:
    """Parse ``C:-1.0,W:0.5`` (or ``A=-1.1``) into an amino-acid bias map."""
    raw = str(text or "").strip()
    if not raw:
        return {}
    result: dict[str, float] = {}
    for token in raw.replace(";", ",").split(","):
        piece = token.strip()
        if not piece:
            continue
        separator = ":" if ":" in piece else "="
        if separator not in piece:
            raise StepError(
                f"proteinmpnn_interface_design: bias token {piece!r} is not of "
                "the form C:-1.0"
            )
        amino_acid, value_text = piece.split(separator, 1)
        amino_acid = amino_acid.strip().upper()
        if len(amino_acid) != 1 or amino_acid not in _AA_ALPHABET:
            raise StepError(
                f"proteinmpnn_interface_design: bias token {piece!r} must name "
                "a single amino acid"
            )
        try:
            result[amino_acid] = float(value_text.strip())
        except ValueError as error:
            raise StepError(
                f"proteinmpnn_interface_design: bias value {value_text.strip()!r} "
                "is not a number"
            ) from error
    return result


def parse_tied_positions(text: str, chains: set[str], residues: dict[str, list[int]]) -> dict[str, list[list[int]]]:
    """Parse ``A:1,B:1;A:2,B:2`` into chain -> list of tied position groups."""
    raw = str(text or "").strip()
    if not raw:
        return {}
    groups: list[list[tuple[str, int]]] = []
    for group in raw.replace("|", ";").split(";"):
        piece = group.strip()
        if not piece:
            continue
        members: list[tuple[str, int]] = []
        for token in piece.split(","):
            if ":" not in token:
                raise StepError(
                    f"proteinmpnn_interface_design: tied position {token!r} is "
                    "not of the form A:12"
                )
            chain, position_text = token.split(":", 1)
            chain = chain.strip()
            if chain not in chains:
                raise StepError(
                    f"proteinmpnn_interface_design: tied position chain "
                    f"{chain!r} is not in the structure"
                )
            try:
                position = int(position_text)
            except ValueError as error:
                raise StepError(
                    f"proteinmpnn_interface_design: tied position "
                    f"{position_text!r} is not an integer"
                ) from error
            if position not in residues.get(chain, []):
                raise StepError(
                    f"proteinmpnn_interface_design: tied position {chain}:"
                    f"{position} is not a residue of the structure"
                )
            members.append((chain, position))
        if len(members) < 2:
            raise StepError(
                "proteinmpnn_interface_design: every tied group needs at least "
                "two positions, e.g. 'A:12,B:12'"
            )
        groups.append(members)
    tied: dict[str, list[list[int]]] = {}
    for members in groups:
        by_chain: dict[str, list[int]] = {}
        for chain, position in members:
            by_chain.setdefault(chain, []).append(position)
        for chain, positions in by_chain.items():
            tied.setdefault(chain, []).append(positions)
    return tied


class ProteinmpnnInterfaceDesignStep(Step):
    provider = 'operon-core'
    """Design one chain of a complex while holding the partner fixed."""
    parameters_file = 'proteinmpnn_interface_design.ProteinmpnnInterfaceDesignStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'proteinmpnn_interface_design',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ProteinMPNN interface design',
     'category': 'Machine Learning',
     'icon': 'Intersect',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': True,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24'],
     'dependency_imports': [],
     'inputs_arity': 0,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Design a binder chain against a fixed partner with the official ProteinMPNN runner, including amino-acid bias, omission and tied positions.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        structure_path = Path(str(params.get("structure_path", "") or "").strip()).expanduser()
        proteinmpnn_path = Path(
            str(params.get("proteinmpnn_path", "") or "").strip()
            or os.environ.get("OPERON_PROTEINMPNN_PATH", "")
        ).expanduser()
        weights_text = str(params.get("weights_path", "") or "").strip()
        python_executable = str(params.get("python_executable", "") or "").strip()
        model_name = str(params.get("model_name", "v_48_020") or "v_48_020").strip()
        num_seq = int(params.get("num_seq_per_target", 4))
        sampling_temp = str(params.get("sampling_temp", "0.1") or "0.1").strip()
        seed = int(params.get("seed", 1))
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        binder_text = str(params.get("binder_chains", "A") or "A").strip()
        target_text = str(params.get("target_chains", "") or "").strip()
        design_ranges = str(params.get("design_ranges", "") or "").strip()
        fixed_extra = str(params.get("fixed_positions", "") or "").strip()
        bias = parse_bias(str(params.get("bias_aa", "") or ""))
        omit = str(params.get("omit_aa", "") or "").replace(",", "").replace(" ", "").strip().upper()
        tied_text = str(params.get("tied_positions", "") or "").strip()
        out_name = params.get("output", self.name)

        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_interface_design: structure_path '{structure_path}' "
                "is not a file"
            )
        if structure_path.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "proteinmpnn_interface_design: structure_path must be a .pdb "
                "file (ProteinMPNN needs atom names)"
            )
        if not proteinmpnn_path.is_dir():
            raise StepError(
                f"proteinmpnn_interface_design: proteinmpnn_path "
                f"'{proteinmpnn_path}' is not a directory (set "
                "OPERON_PROTEINMPNN_PATH or the proteinmpnn_path parameter)"
            )
        runner = proteinmpnn_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_interface_design: '{runner}' does not exist; point "
                "proteinmpnn_path at the official ProteinMPNN checkout"
            )
        if model_name not in MODELS:
            raise StepError(
                "proteinmpnn_interface_design: model_name must be one of "
                f"{list(MODELS)}"
            )
        if num_seq < 1:
            raise StepError(
                "proteinmpnn_interface_design: num_seq_per_target must be >= 1"
            )
        if not sampling_temp:
            raise StepError("proteinmpnn_interface_design: sampling_temp must not be empty")
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_interface_design: device must be 'cpu' or 'cuda'")
        if bool(omit) and not set(omit) <= set(_AA_ALPHABET):
            raise StepError(
                "proteinmpnn_interface_design: omit_aa must only list amino "
                "acids, got " + repr(omit)
            )
        weights_path = (
            Path(weights_text).expanduser()
            if weights_text
            else proteinmpnn_path / "vanilla_model_weights"
        )
        weight_file = weights_path / f"{model_name}.pt"
        if not weight_file.is_file():
            raise StepError(
                f"proteinmpnn_interface_design: weights '{weight_file}' not "
                "found; set weights_path to the directory holding v_48_*.pt"
            )

        chains = pdb_chains(structure_path)
        binder = binder_text.replace(",", " ").split()
        if not binder:
            raise StepError("proteinmpnn_interface_design: binder_chains must not be empty")
        target = sorted(set(chains) - set(binder)) if not target_text else target_text.replace(",", " ").split()
        if not target:
            raise StepError(
                "proteinmpnn_interface_design: the structure has no chain left "
                "as the fixed target; give binder_chains and target_chains"
            )
        missing = [chain for chain in binder + target if chain not in chains]
        if missing:
            raise StepError(
                "proteinmpnn_interface_design: chain(s) "
                f"{missing} not found in {structure_path.name}; chains are "
                f"{sorted(chains)}"
            )
        overlap = set(binder) & set(target)
        if overlap:
            raise StepError(
                "proteinmpnn_interface_design: chain(s) "
                f"{sorted(overlap)} cannot be designed and fixed at once"
            )

        fixed: dict[str, list[int]] = {}
        if design_ranges:
            ranges = parse_positions(design_ranges)
            unknown_range_chains = sorted(set(ranges) - set(chains))
            if unknown_range_chains:
                raise StepError(
                    "proteinmpnn_interface_design: design_ranges names chain(s) "
                    f"{unknown_range_chains} that are not in the structure"
                )
            for chain in binder:
                designed = set(ranges.get(chain, []))
                fixed[chain] = [
                    position for position in chains[chain]
                    if position not in designed
                ]
            for chain in ranges:
                unknown = [position for position in ranges[chain] if position not in chains[chain]]
                if unknown:
                    raise StepError(
                        "proteinmpnn_interface_design: design_ranges position(s) "
                        f"{unknown[:5]} are not residues of chain {chain}"
                    )
        if fixed_extra:
            for chain, positions in parse_positions(fixed_extra).items():
                if chain not in chains:
                    raise StepError(
                        "proteinmpnn_interface_design: fixed_positions names "
                        f"chain {chain!r} that is not in the structure"
                    )
                unknown = [position for position in positions if position not in chains[chain]]
                if unknown:
                    raise StepError(
                        "proteinmpnn_interface_design: fixed_positions "
                        f"position(s) {unknown[:5]} are not residues of chain {chain}"
                    )
                fixed.setdefault(chain, []).extend(positions)
        for chain in target:
            fixed.setdefault(chain, []).extend(chains[chain])
        fixed = {chain: sorted(set(fixed.get(chain, []))) for chain in chains}
        tied = parse_tied_positions(tied_text, set(chains), chains) if tied_text else {}

        out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-interface-"))
        pdb_key = structure_path.stem
        started = time.monotonic()
        try:
            command = [
                python_executable or sys.executable,
                runner.as_posix(),
                "--pdb_path", structure_path.as_posix(),
                "--out_folder", out_dir.as_posix(),
                "--pdb_path_chains", " ".join(binder),
                "--num_seq_per_target", str(num_seq),
                "--sampling_temp", sampling_temp,
                "--seed", str(seed),
                "--path_to_model_weights", weights_path.as_posix(),
                "--model_name", model_name,
                "--suppress_print", "1",
            ]
            if fixed:
                fixed_file = out_dir / "fixed.jsonl"
                fixed_file.write_text(json.dumps({pdb_key: fixed}), encoding="utf-8")
                command.extend(["--fixed_positions_jsonl", fixed_file.as_posix()])
            if bias:
                bias_file = out_dir / "bias.jsonl"
                bias_file.write_text(json.dumps(bias), encoding="utf-8")
                command.extend(["--bias_AA_jsonl", bias_file.as_posix()])
            if omit:
                command.extend(["--omit_AAs", omit])
            if tied:
                tied_file = out_dir / "tied.jsonl"
                tied_file.write_text(json.dumps({pdb_key: tied}), encoding="utf-8")
                command.extend(["--tied_positions_jsonl", tied_file.as_posix()])
            environment = dict(os.environ)
            if device == "cpu":
                environment["CUDA_VISIBLE_DEVICES"] = ""
            completed = subprocess.run(
                command,
                cwd=str(proteinmpnn_path),
                env=environment,
                capture_output=True,
                text=True,
                timeout=float(params.get("timeout_seconds", 3600.0)),
                check=False,
            )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()[-1200:]
                raise StepError(
                    "proteinmpnn_interface_design: the official runner failed "
                    f"with exit code {completed.returncode}: {tail}"
                )
            fasta = out_dir / "seqs" / f"{structure_path.stem}.fa"
            if not fasta.is_file():
                raise StepError(
                    "proteinmpnn_interface_design: the official runner produced "
                    f"no design FASTA at '{fasta}'"
                )
            records = parse_design_fasta(fasta)
            if not records:
                raise StepError(
                    "proteinmpnn_interface_design: the design FASTA holds no "
                    "generated sequences"
                )
            if any(
                not math.isfinite(float(record.get(key, float("nan"))))
                for record in records
                for key in ("score", "global_score")
            ):
                raise StepError(
                    "proteinmpnn_interface_design: the official runner returned "
                    "non-finite scores; check that the PDB carries N, CA, C and O "
                    "backbone atoms for every designed residue"
                )
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
        elapsed = time.monotonic() - started
        rows = [[record["score"], record["global_score"], record["seq_recovery"]] for record in records]
        labels = {f"design{record['sample']}": index for index, record in enumerate(records)}
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["design", "statistic"],
            labels={
                "design": labels,
                "statistic": {name: index for index, name in enumerate(STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequences": [record["sequence"] for record in records],
                "structure_path": structure_path.as_posix(),
                "binder_chains": binder,
                "target_chains": target,
                "model_name": model_name,
                "sampling_temp": sampling_temp,
                "seed": seed,
                "device": device,
                "bias": bias,
                "omit": list(omit),
                "tied_positions": tied,
                "fixed_positions": fixed,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(records),
            "binder_chains": binder,
            "target_chains": target,
            "sequences": [record["sequence"] for record in records],
            "scores": [record["score"] for record in records],
            "elapsed_seconds": round(elapsed, 3),
        }
        print(
            f"[proteinmpnn_interface_design] {len(records)} designs for binder "
            f"{'/'.join(binder)} against {'/'.join(target)} ({elapsed:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
