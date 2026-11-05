import inspect

import pytest

from src.task.step.steps.esm_embedding_outlier_scan import EsmEmbeddingOutlierScanStep
from src.task.step.steps.esm_if_masked_region_scan import EsmIfMaskedRegionScanStep
from src.task.step.steps.esm_if_mutation_scan import EsmIfMutationScanStep
from src.task.step.steps.proteinmpnn_interface_redesign import ProteinmpnnInterfaceRedesignStep
from src.task.step.steps.proteinmpnn_native_recovery_scan import ProteinmpnnNativeRecoveryScanStep
from src.task.step.steps.proteinmpnn_perplexity import ProteinmpnnPerplexityStep
from src.task.step.steps.rdkit_pharmacophore_features import RdkitPharmacophoreFeaturesStep
from src.task.step.steps.rdkit_scaffold_diversity import RdkitScaffoldDiversityStep
from src.task.step.steps.sequence_gc_profile import SequenceGcProfileStep
from src.task.step.steps.sequence_kmer_profile import SequenceKmerProfileStep
from src.task.step.steps.structure_cavity_scan import StructureCavityScanStep
from src.task.step.steps.structure_helix_geometry import StructureHelixGeometryStep

STEPS = [
    EsmEmbeddingOutlierScanStep,
    EsmIfMaskedRegionScanStep,
    EsmIfMutationScanStep,
    ProteinmpnnInterfaceRedesignStep,
    ProteinmpnnNativeRecoveryScanStep,
    ProteinmpnnPerplexityStep,
    RdkitPharmacophoreFeaturesStep,
    RdkitScaffoldDiversityStep,
    SequenceGcProfileStep,
    SequenceKmerProfileStep,
    StructureCavityScanStep,
    StructureHelixGeometryStep,
]


@pytest.mark.parametrize("step", STEPS, ids=[s.__name__ for s in STEPS])
def test_estimate_memory_contract(step):
    """The planner calls cls.estimate_memory(inputs, params, profiles) -> (ws, out)."""
    attr = inspect.getattr_static(step, "estimate_memory")
    assert isinstance(attr, classmethod), f"{step.__name__} must use @classmethod"
    workspace, output = step.estimate_memory([], {}, {})
    assert isinstance(workspace, int) and workspace >= 0
    assert isinstance(output, int) and output >= 0
