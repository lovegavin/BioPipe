"""structure_ligand_redock_qc: PoseBusters redock validation of a docked pose."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def run_redock(
    complex_path: Path,
    ligand_path: Path,
    pose_path: Path,
    *,
    full_report: bool = True,
) -> "object":
    """Run PoseBusters in redock mode and return the report DataFrame."""

    for label, path in (("complex_path", complex_path), ("ligand_path", ligand_path), ("pose_path", pose_path)):
        if not Path(path).expanduser().is_file():
            raise StepError(f"structure_ligand_redock_qc: {label} {path} is not a file")
    try:
        from posebusters import PoseBusters
    except ImportError:
        raise StepError(
            "structure_ligand_redock_qc: posebusters is required; install it with 'python -m pip install posebusters'"
        ) from None
    buster = PoseBusters(config="redock")
    report = buster.bust(
        mol_pred=str(Path(pose_path).expanduser()),
        mol_true=str(Path(ligand_path).expanduser()),
        mol_cond=str(Path(complex_path).expanduser()),
        full_report=bool(full_report),
    )
    if report is None or len(report) == 0:
        raise StepError("structure_ligand_redock_qc: posebusters returned an empty report")
    return report


def redock_rows(report: "object", *, legend: dict) -> tuple[list[dict], dict]:
    """Extract the RMSD metrics and the pass/fail summary from a redock report."""

    row = report.iloc[0]
    metrics = []
    for name in ("rmsd", "kabsch_rmsd", "centroid_distance"):
        if name in report.columns:
            value = row[name]
            metrics.append({"metric": name, "value": float(value) if value == value else float("nan")})
    checks = {}
    for column in report.columns:
        value = row[column]
        if isinstance(value, (bool, np.bool_)):
            checks[str(column)] = bool(value)
    failed = sorted(name for name, passed in checks.items() if not passed)
    summary = {
        "n_checks": len(checks),
        "n_failed": len(failed),
        "failed_checks": failed,
        "rmsd_pass": bool(checks.get("rmsd_≤_2å", False)),
        "legend": legend,
    }
    return metrics, summary


class StructureLigandRedockQcStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ligand_redock_qc.StructureLigandRedockQcStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_redock_qc",
        "version": "1.0.0",
        "kind": "operator",
        "title": "配体 redock 几何校验",
        "description": (
            "Validate a docked ligand pose against a crystal ligand and its protein with "
            "PoseBusters redock mode, reporting symmetry-aware RMSD and failed checks."
        ),
        "category": "Structure",
        "icon": "Flask",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["posebusters"],
        "dependency_imports": ["posebusters"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        report = run_redock(
            Path(str(params.get("complex_path", ""))),
            Path(str(params.get("ligand_path", ""))),
            Path(str(params.get("pose_path", ""))),
            full_report=bool(params.get("full_report", True)),
        )
        legend = {
            "complex_path": str(params.get("complex_path", "")),
            "ligand_path": str(params.get("ligand_path", "")),
            "pose_path": str(params.get("pose_path", "")),
        }
        metrics, summary = redock_rows(report, legend=legend)
        data = np.asarray([[metric["value"]] for metric in metrics], dtype=np.float32)
        out_dim = str(params.get("metric_dim", "metric"))
        out_name = str(params.get("output", "redock"))
        info = {"missing_code": np.nan}
        info.update({key: value for key, value in summary.items() if key != "legend"})
        info["paths"] = legend
        ctx[out_name] = Form(
            data=data,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {metric["metric"]: index for index, metric in enumerate(metrics)},
                "statistic": {"value": 0},
            },
            info=info,
        )
        self._export_data = {"rmsd": summary.get("rmsd_pass"), "n_failed": summary.get("n_failed"), "metrics": metrics}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
