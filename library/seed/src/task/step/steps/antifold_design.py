"""antifold_design: AntiFold antibody inverse-folding redesign."""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
_HEADER = re.compile(r"score=(-?\d+\.\d+),\s*global_score=(-?\d+\.\d+)")


def parse_fasta(path: Path) -> list[dict]:
    """Parse the AntiFold FASTA (wild type record first, then sampled designs)."""

    if not path.is_file():
        raise StepError(f"antifold_design: no FASTA was written at {path}")
    records: list[dict] = []
    name = ""
    chunks: list[str] = []
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if name:
                records.append(_record(name, "".join(chunks)))
            name = line[1:].strip()
            chunks = []
        elif line.strip():
            chunks.append(line.strip())
    if name:
        records.append(_record(name, "".join(chunks)))
    if not records:
        raise StepError(f"antifold_design: no designs were found in {path}")
    return records


def _record(header: str, sequence: str) -> dict:
    match = _HEADER.search(header)
    fields = dict(re.findall(r"(sample|mutations|seq_recovery|T)=([0-9.]+)", header))
    return {
        "header": header,
        "sequence": sequence,
        "score": float(match.group(1)) if match else float("nan"),
        "global_score": float(match.group(2)) if match else float("nan"),
        "seq_recovery": float(fields["seq_recovery"]) if "seq_recovery" in fields else float("nan"),
        "mutations": int(float(fields["mutations"])) if "mutations" in fields else 0,
        "temperature": float(fields["T"]) if "T" in fields else float("nan"),
        "sample": int(float(fields["sample"])) if "sample" in fields else 0,
        "is_wildtype": "sample=" not in header,
        "regions": re.search(r"regions=\[([^\]]*)\]", header).group(1) if "regions=" in header else "",
    }


def parse_profile(path: Path) -> list[dict]:
    """Parse the per-residue log-probability CSV written by AntiFold."""

    if not path.is_file():
        raise StepError(f"antifold_design: no log-probability CSV was written at {path}")
    rows: list[dict] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            wild = str(record.get("pdb_res", "")).strip().upper()
            top = str(record.get("top_res", "")).strip().upper()
            try:
                position = int(float(record.get("pdb_pos", "nan")))
                perplexity = float(record.get("perplexity", "nan"))
            except (TypeError, ValueError):
                continue
            wild_prob = record.get(wild)
            top_prob = record.get(top)
            rows.append(
                {
                    "position": position,
                    "chain": str(record.get("pdb_chain", "")).strip(),
                    "wild_type": wild,
                    "preferred": top,
                    "perplexity": perplexity,
                    "wild_type_logprob": float(wild_prob) if wild_prob not in (None, "") else float("nan"),
                    "preferred_logprob": float(top_prob) if top_prob not in (None, "") else float("nan"),
                    "is_preferred": bool(wild != top),
                }
            )
    if not rows:
        raise StepError(f"antifold_design: the profile at {path} holds no residue rows")
    return rows


def profile_summary(rows: list[dict]) -> dict:
    """Summarise a profile: preferred substitutions and mean perplexity."""

    changes = [row for row in rows if row["is_preferred"]]
    return {
        "n_residues": len(rows),
        "n_preferred_changes": len(changes),
        "n_preferred_identical": len(rows) - len(changes),
        "mean_perplexity": float(np.mean([row["perplexity"] for row in rows])),
    }


def antifold_command(
    structure: Path,
    out_dir: Path,
    *,
    python_executable: str = "",
    nanobody_chain: str = "",
    heavy_chain: str = "",
    light_chain: str = "",
    antigen_chain: str = "",
    regions: str = "CDR1 CDR2 CDR3",
    num_seq_per_target: int = 5,
    sampling_temp: str = "0.2",
    seed: int = 42,
    limit_variation: bool = False,
    runner_path: str = "",
) -> list[str]:
    """Build the official AntiFold command line."""

    if not python_executable:
        from operon.environments import resolve
        resolved = resolve('antifold')
        python_executable = str(resolved) if resolved else ''
    launcher = python_executable or sys.executable
    entry = [str(runner_path)] if runner_path else ["-m", "antifold.main"]
    command = [
        launcher,
        *entry,
        "--pdb_file",
        structure.as_posix(),
        "--out_dir",
        out_dir.as_posix(),
        "--num_seq_per_target",
        str(num_seq_per_target),
        "--sampling_temp",
        str(sampling_temp),
        "--seed",
        str(seed),
    ]
    if nanobody_chain:
        command.extend(["--nanobody_chain", nanobody_chain])
    if heavy_chain:
        command.extend(["--heavy_chain", heavy_chain])
    if light_chain:
        command.extend(["--light_chain", light_chain])
    if antigen_chain:
        command.extend(["--antigen_chain", antigen_chain])
    if regions:
        command.extend(["--regions", regions])
    if limit_variation:
        command.append("--limit_variation")
    return command


def run_antifold(command: list[str], out_dir: Path, *, timeout: int = 1800) -> tuple[list[dict], list[dict], Path, Path]:
    """Run AntiFold and return the parsed designs and profile."""

    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"antifold_design: the predictor timed out after {timeout} s") from exc
    except FileNotFoundError as exc:
        raise StepError(f"antifold_design: the predictor interpreter was not found: {exc}") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-4:]
        raise StepError("antifold_design: the predictor failed with exit code " + str(completed.returncode) + ": " + " | ".join(tail))
    fasta = sorted(out_dir.glob("*.fasta"))
    csvs = sorted(out_dir.glob("*.csv"))
    if not fasta:
        raise StepError(f"antifold_design: no FASTA was written under {out_dir}")
    if not csvs:
        raise StepError(f"antifold_design: no log-probability CSV was written under {out_dir}")
    return parse_fasta(fasta[0]), parse_profile(csvs[0]), fasta[0], csvs[0]


class AntifoldDesignStep(Step):
    provider = "operon-core"
    parameters_file = "antifold_design.AntifoldDesignStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antifold_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AntiFold 抗体逆折叠设计",
        "description": (
            "Run the official AntiFold antibody inverse-folding model on a PDB "
            "structure, returning sampled sequences with scores and a per-residue "
            "log-probability profile."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "antifold"},
        "dependencies": ["antifold", "torch"],
        "dependency_imports": ["antifold"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        structure = Path(str(params.get("structure_path", ""))).expanduser()
        if not structure.is_file():
            raise StepError(f"antifold_design: structure_path {structure} is not a file")
        if structure.suffix.lower() != ".pdb":
            raise StepError("antifold_design: structure_path must be a .pdb file")
        nanobody = str(params.get("nanobody_chain", "")).strip()
        heavy = str(params.get("heavy_chain", "")).strip()
        light = str(params.get("light_chain", "")).strip()
        if not (nanobody or heavy or light):
            raise StepError("antifold_design: declare at least one antibody chain (nanobody_chain, heavy_chain or light_chain)")
        workdir = Path(tempfile.mkdtemp(prefix="antifold_"))
        out_dir = workdir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        command = antifold_command(
            structure,
            out_dir,
            python_executable=str(params.get("python_executable", "")),
            nanobody_chain=nanobody,
            heavy_chain=heavy,
            light_chain=light,
            antigen_chain=str(params.get("antigen_chain", "")),
            regions=str(params.get("regions", "CDR1 CDR2 CDR3")),
            num_seq_per_target=int(params.get("num_seq_per_target", 5)),
            sampling_temp=str(params.get("sampling_temp", "0.2")),
            seed=int(params.get("seed", 42)),
            limit_variation=bool(params.get("limit_variation", False)),
            runner_path=str(params.get("runner_path", "")),
        )
        records, profile, fasta_path, csv_path = run_antifold(command, out_dir, timeout=int(params.get("timeout_seconds", 1800)))
        wild = next((record for record in records if record["is_wildtype"]), records[0])
        designs = [record for record in records if not record["is_wildtype"]]
        if not designs:
            raise StepError("antifold_design: the predictor returned no sampled design")
        statistics = ("score", "global_score", "seq_recovery", "n_mutations")
        data = np.zeros((len(designs), len(statistics)), dtype=np.float32)
        for index, record in enumerate(designs):
            data[index] = [record["score"], record["global_score"], record["seq_recovery"], record["mutations"]]
        out_name = str(params.get("output", "designs"))
        ctx[out_name] = Form(
            data=data,
            dims=[str(params.get("design_dim", "design")), "statistic"],
            labels={
                str(params.get("design_dim", "design")): {f"design{index + 1}": index for index in range(len(designs))},
                "statistic": {name: index for index, name in enumerate(statistics)},
            },
            info={
                "missing_code": np.nan,
                "wild_type_sequence": wild["sequence"],
                "wild_type_score": wild["score"],
                "sequences": [record["sequence"] for record in designs],
                "regions": wild.get("regions", ""),
                "model": "AntiFold",
                "temperature": designs[0]["temperature"],
                "profile_summary": profile_summary(profile),
                "n_designs": len(designs),
                "fasta": fasta_path.name,
                "profile_csv": csv_path.name,
            },
        )
        self._export_data = {
            "designs": designs,
            "wild_type": wild,
            "profile": profile,
            "profile_summary": profile_summary(profile),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
