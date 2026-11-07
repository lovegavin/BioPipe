"""AntiFold inverse-folding scores for antibody structures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step import Step

_IMGT = {"CDR1": (27, 38), "CDR2": (56, 65), "CDR3": (105, 117)}


def _region_mask(position: int, regions: tuple[str, ...]) -> int:
    for name in regions:
        low, high = _IMGT[name]
        if low <= position <= high:
            return 1
    return 0


def parse_regions(text: str) -> tuple[str, ...]:
    names = tuple(part.strip().upper() for part in str(text).replace(";", ",").split(",") if part.strip())
    if not names:
        raise StepError("antifold_score: imgt_regions must list at least one region")
    unknown = [name for name in names if name not in _IMGT]
    if unknown:
        raise StepError(f"antifold_score: unknown IMGT region(s) {unknown}; choose from {sorted(_IMGT)}")
    return names


def parse_posins(value: str) -> int:
    digits = "".join(char for char in str(value) if char.isdigit())
    if not digits:
        raise StepError(f"antifold_score: cannot read an IMGT position from '{value}'")
    return int(digits)


def _import_antifold():
    try:
        import biotite.structure as structure
        if not hasattr(structure, "filter_backbone"):
            structure.filter_backbone = structure.filter_peptide_backbone
        from antifold import antiscripts
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError(
            "antifold_score: the 'antifold' package is required; install it with "
            "'python -m pip install antifold'"
        ) from exc
    return antiscripts


def load_scoring_model(weights_path: str):
    antiscripts = _import_antifold()
    path = Path(weights_path).expanduser()
    if not path.is_file():
        raise StepError(
            f"antifold_score: weights file {path} does not exist; download model.pt from "
            "https://opig.stats.ox.ac.uk/data/downloads/AntiFold/models/model.pt"
        )
    try:
        model, _ = antiscripts.antifold.esm.pretrained._load_IF1_local()
    except Exception as exc:  # pragma: no cover - weight layout varies
        raise StepError(f"antifold_score: cannot build the ESM-IF backbone: {exc}") from exc
    model = antiscripts.load_IF1_checkpoint(model, str(path))
    return model.eval()


def score_dataframe(frame, regions: tuple[str, ...]) -> list[dict]:
    rows: list[dict] = []
    for _, item in frame.iterrows():
        position = parse_posins(item["pdb_posins"])
        residue = str(item["pdb_res"])
        probabilities = np.array([float(item[aa]) for aa in "ACDEFGHIKLMNPQRSTVWY"], dtype=np.float64)
        probabilities = np.clip(probabilities, 1e-12, 1.0)
        probabilities = probabilities / probabilities.sum()
        entropy = float(-(probabilities * np.log(probabilities)).sum())
        rows.append(
            {
                "chain": str(item["pdb_chain"]),
                "position": position,
                "residue": residue,
                "perplexity": float(item["perplexity"]),
                "log_prob": float(np.log(probabilities["ACDEFGHIKLMNPQRSTVWY".index(residue)])),
                "entropy": entropy,
                "is_cdr": _region_mask(position, regions),
            }
        )
    return rows


def _score_file(model, antiscripts, structure_path: Path, chain: str, batch_size: int) -> list[dict]:
    import pandas as pd

    workdir = Path(tempfile.mkdtemp(prefix="antifold_"))
    target = workdir / structure_path.name
    target.write_text(structure_path.read_text(encoding="utf-8"), encoding="utf-8")
    frame = pd.DataFrame([{"pdb": structure_path.stem, "Hchain": chain}])
    try:
        frames = antiscripts.get_pdbs_logits(
            model, frame, str(workdir), batch_size=batch_size, custom_chain_mode=True
        )
    except Exception as exc:
        raise StepError(f"antifold_score: AntiFold prediction failed: {exc}") from exc
    if not frames:
        raise StepError("antifold_score: AntiFold returned no scores")
    return list(frames[0].to_dict("records"))


class AntifoldScoreStep(Step):
    provider = "operon-core"
    parameters_file = "antifold_score.AntifoldScoreStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antifold_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AntiFold inverse-folding scores",
        "description": "Per-residue AntiFold perplexity and native log-probability for an antibody structure.",
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "version": 1,
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": False,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "antifold"},
        "dependencies": [],
        "dependency_imports": ["antifold", "pandas", "torch"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def _export_summary(self, form: Form) -> dict:
        return {
            "dims": list(form.dims),
            "labels": {name: dict(mapping) for name, mapping in form.labels.items()},
            "info": {key: value for key, value in form.info.items() if key != "missing_code"},
        }

    def run(self, ctx, inputs):
        params = ctx.step_params
        raw_path = str(params.get("structure_path", "") or "").strip()
        if not raw_path:
            raise StepError("antifold_score: structure_path is required")
        structure_path = Path(raw_path).expanduser()
        if not structure_path.is_file():
            raise StepError(f"antifold_score: structure_path {structure_path} is not a file")
        if structure_path.suffix.lower() not in (".pdb", ".ent"):
            raise StepError("antifold_score: structure_path must name a .pdb file")
        chain = str(params.get("chains", "") or "").strip().upper()
        if not chain:
            raise StepError("antifold_score: chains must name one antibody chain")
        if "," in chain:
            raise StepError("antifold_score: score one chain per run; split multi-chain files first")
        regions = parse_regions(str(params.get("imgt_regions", "CDR1,CDR2,CDR3")))
        weights = str(params.get("weights_path", "") or "").strip()
        if not weights:
            raise StepError(
                "antifold_score: weights_path is required; download model.pt from "
                "https://opig.stats.ox.ac.uk/data/downloads/AntiFold/models/model.pt"
            )
        device = str(params.get("device", "cpu")).lower()
        if device not in ("cpu", "cuda"):
            raise StepError("antifold_score: device must be 'cpu' or 'cuda'")
        if device == "cpu":
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
        model = load_scoring_model(weights)
        antiscripts = _import_antifold()
        records = _score_file(model, antiscripts, structure_path, chain, int(params.get("batch_size", 1)))
        rows = score_dataframe_from_records(records, regions)
        if not rows:
            raise StepError("antifold_score: no residue was scored")
        rows.sort(key=lambda item: (item["position"], item["residue"]))
        data = np.array(
            [[item["perplexity"], item["log_prob"], item["entropy"], item["is_cdr"]] for item in rows],
            dtype=np.float32,
        )
        residue_dim = str(params.get("residue_dim", "residue"))
        labels = {f"{item['chain']}:{item['position']}": index for index, item in enumerate(rows)}
        info = {
            "n_residues": len(rows),
            "mean_perplexity": float(np.mean([item["perplexity"] for item in rows])),
            "cdr_residues": int(sum(item["is_cdr"] for item in rows)),
            "imgt_regions": list(regions),
            "chain": chain,
            "weights_path": str(Path(weights).expanduser()),
        }
        form = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={residue_dim: labels, "statistic": {"perplexity": 0, "log_prob": 1, "entropy": 2, "is_cdr": 3}},
            info={"missing_code": np.nan, **info},
        )
        ctx[str(params.get("output", "scores"))] = form
        self._export_data = self._export_summary(form)


def score_dataframe_from_records(records: list[dict], regions: tuple[str, ...]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        position = parse_posins(record["pdb_posins"])
        residue = str(record["pdb_res"])
        probabilities = np.array([float(record[aa]) for aa in "ACDEFGHIKLMNPQRSTVWY"], dtype=np.float64)
        probabilities = np.clip(probabilities, 1e-12, 1.0)
        probabilities = probabilities / probabilities.sum()
        entropy = float(-(probabilities * np.log(probabilities)).sum())
        rows.append(
            {
                "chain": str(record["pdb_chain"]),
                "position": position,
                "residue": residue,
                "perplexity": float(record["perplexity"]),
                "log_prob": float(np.log(probabilities["ACDEFGHIKLMNPQRSTVWY".index(residue)])),
                "entropy": entropy,
                "is_cdr": _region_mask(position, regions),
            }
        )
    return rows
