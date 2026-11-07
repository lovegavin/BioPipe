from pathlib import Path
import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.core.encoding import LabelEncoder
from src.task.context import Context
from src.task.step.steps.chain_coverage_summary import ChainCoverageSummaryStep
from src.task.step.steps.liftover_intervals import LiftoverIntervalsStep
from src.task.step.steps.liftover_variants import LiftoverVariantsStep

TAB = chr(9)
NL = chr(10)

CHAIN = (
    "chain 100 chr1 1000 + 100 200 chrA 900 + 500 600 1" + NL
    + "50" + TAB + "10" + TAB + "10" + NL
    + "40" + NL
    + NL
    + "chain 100 chr2 1000 + 10 60 chrB 800 - 100 150 2" + NL
    + "50" + NL
)

BED_ROWS = [
    ("chr1", 100, 150, "+"),
    ("chr2", 10, 60, "+"),
]

VCF = (
    "##fileformat=VCFv4.2" + NL
    + "##source=test" + NL
    + "#CHROM" + TAB + "POS" + TAB + "ID" + TAB + "REF" + TAB + "ALT" + TAB
    + "QUAL" + TAB + "FILTER" + TAB + "INFO" + NL
    + "chr1" + TAB + "101" + TAB + "." + TAB + "A" + TAB + "G" + TAB + "50"
    + TAB + "PASS" + TAB + "." + NL
    + "chr2" + TAB + "20" + TAB + "." + TAB + "AC" + TAB + "GT" + TAB + "60"
    + TAB + "PASS" + TAB + "." + NL
    + "chr1" + TAB + "155" + TAB + "." + TAB + "A" + TAB + "T" + TAB + "."
    + TAB + "PASS" + TAB + "." + NL
)


class Ctx(Context):
    def __init__(self, params, root):
        self.step_params = params
        self._values = {}
        self._root = root

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]

    def artifact_path(self, name):
        return self._root / name


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def chain_artifact(path):
    return FileArtifact("chain", {"chain": path}, info={"representation": "chain"})


def bed_form():
    chrom_encoder = LabelEncoder()
    chrom_codes = chrom_encoder.fit_transform([row[0] for row in BED_ROWS])
    strand_encoder = LabelEncoder()
    strand_codes = strand_encoder.fit_transform([row[3] for row in BED_ROWS])
    data = np.array(
        [
            [float(chrom_codes[index]), float(row[1]), float(row[2]), float(strand_codes[index])]
            for index, row in enumerate(BED_ROWS)
        ]
    )
    labels = {"chrom": 0, "chromStart": 1, "chromEnd": 2, "strand": 3}
    return Form(
        data,
        dims=["region", "field"],
        labels={"region": {f"i{index}": index for index in range(len(BED_ROWS))}, "field": labels},
        info={"encoders": {"field": {"chrom": chrom_encoder, "strand": strand_encoder}}},
    )


def test_load_and_map_chain(tmp_path):
    from src.task.step.steps._liftover_utils import ChainIndex, load_chain

    chains = load_chain(write(tmp_path / "test.chain", CHAIN))
    assert len(chains) == 2
    assert chains[0]["t_name"] == "chr1"
    assert int(sum(block[0] for block in chains[0]["blocks"])) == 90
    index = ChainIndex(chains)
    assert index.map_interval("chr1", 100, 150) == ("chrA", 500, 550, "+")
    assert index.map_interval("chr1", 160, 200) == ("chrA", 560, 600, "+")
    assert index.map_interval("chr1", 150, 160) is None
    assert index.map_interval("chr2", 10, 60) == ("chrB", 650, 700, "-")


def test_intervals_write_native_bed(tmp_path):
    chain = write(tmp_path / "test.chain", CHAIN)
    ctx = Ctx({"output": "lift"}, tmp_path / "out")
    step = LiftoverIntervalsStep()
    step.name = "liftover_intervals"
    step.run(ctx, [bed_form(), chain_artifact(chain)])
    artifact = ctx["lift"]
    mapped = Path(artifact.files["mapped"]).read_text().splitlines()
    unmapped = Path(artifact.files["unmapped"]).read_text().splitlines()
    assert mapped[0].split(TAB)[:3] == ["chrA", "500", "550"]
    assert mapped[1].split(TAB)[0] == "chrB"
    assert mapped[1].split(TAB)[5] == "-"
    assert unmapped == []


def test_variants_reverse_complement(tmp_path):
    chain = write(tmp_path / "test.chain", CHAIN)
    vcf = write(tmp_path / "in.vcf", VCF)
    ctx = Ctx({"output": "lift"}, tmp_path / "out")
    step = LiftoverVariantsStep()
    step.name = "liftover_variants"
    step.run(ctx, [FileArtifact("vcf", {"vcf": vcf}), chain_artifact(chain)])
    artifact = ctx["lift"]
    mapped = [line for line in Path(artifact.files["mapped"]).read_text().splitlines() if not line.startswith("#")]
    unmapped = [line for line in Path(artifact.files["unmapped"]).read_text().splitlines() if not line.startswith("#")]
    assert mapped[0].split(TAB)[:5] == ["chrA", "501", ".", "A", "G"]
    assert mapped[1].split(TAB)[:5] == ["chrB", "690", ".", "GT", "AC"]
    assert unmapped[0].split(TAB)[:2] == ["chr1", "155"]
    summary = step.export(ctx)
    assert summary["n_mapped"] == 2
    assert summary["n_unmapped"] == 1
    assert summary["n_reverse_complemented"] == 1


def test_coverage_summary_form(tmp_path):
    chain = write(tmp_path / "test.chain", CHAIN)
    ctx = Ctx({"chrom": "chr1"}, tmp_path / "out")
    step = ChainCoverageSummaryStep()
    step.name = "chain_coverage_summary"
    step.run(ctx, [chain_artifact(chain)])
    form = ctx["chain_coverage"]
    assert form.data.shape == (1, 5)
    assert list(form.labels["chrom"]) == ["chr1"]
    assert form.data[0, 0] == 1
    assert form.data[0, 1] == 90
    assert form.data[0, 2] == 90
    assert form.data[0, 3] == pytest.approx(0.09)


def test_missing_chain_file(tmp_path):
    class Missing:
        files = {"chain": tmp_path / "missing.chain"}

    ctx = Ctx({}, tmp_path / "out")
    step = ChainCoverageSummaryStep()
    step.name = "chain_coverage_summary"
    with pytest.raises(StepError, match="chain file not found"):
        step.run(ctx, [Missing()])
