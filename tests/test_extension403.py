import numpy as np
import pytest

from src.core import FileArtifact, Form
from src.core.errors import StepError
from src.task.step.steps.fba_flux_distribution import FbaFluxDistributionStep
from src.task.step.steps.fba_flux_variability import FbaFluxVariabilityStep
from src.task.step.steps.fba_gene_knockout import FbaGeneKnockoutStep
from src.task.step.steps._fba_utils import parse_sbml

MODEL = """<?xml version="1.0" encoding="UTF-8"?>
<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"
      xmlns:fbc="http://www.sbml.org/sbml/level3/version1/fbc/version2"
      level="3" version="1" fbc:required="false">
  <model id="toy">
    <listOfCompartments>
      <compartment id="c" size="1" constant="true"/>
    </listOfCompartments>
    <listOfSpecies>
      <species id="A" compartment="c" boundaryCondition="false" hasOnlySubstanceUnits="false" constant="false"/>
      <species id="B" compartment="c" boundaryCondition="false" hasOnlySubstanceUnits="false" constant="false"/>
      <species id="C" compartment="c" boundaryCondition="false" hasOnlySubstanceUnits="false" constant="false"/>
    </listOfSpecies>
    <listOfParameters>
      <parameter id="cobra_default_ub" value="1000" constant="true" fbc:constant="true"/>
      <parameter id="cobra_0_bound" value="0" constant="true" fbc:constant="true"/>
      <parameter id="up_10" value="10" constant="true" fbc:constant="true"/>
    </listOfParameters>
    <listOfReactions>
      <reaction id="R_EX" reversible="false" fbc:lowerFluxBound="cobra_0_bound" fbc:upperFluxBound="up_10">
        <listOfProducts>
          <speciesReference species="A" stoichiometry="1" constant="true"/>
        </listOfProducts>
      </reaction>
      <reaction id="R1" reversible="false" fbc:lowerFluxBound="cobra_0_bound" fbc:upperFluxBound="cobra_default_ub">
        <listOfReactants><speciesReference species="A" stoichiometry="1" constant="true"/></listOfReactants>
        <listOfProducts><speciesReference species="B" stoichiometry="1" constant="true"/></listOfProducts>
        <fbc:geneProductAssociation>
          <fbc:geneProductRef fbc:geneProduct="g1"/>
        </fbc:geneProductAssociation>
      </reaction>
      <reaction id="R2" reversible="false" fbc:lowerFluxBound="cobra_0_bound" fbc:upperFluxBound="cobra_default_ub">
        <listOfReactants><speciesReference species="B" stoichiometry="1" constant="true"/></listOfReactants>
        <listOfProducts><speciesReference species="C" stoichiometry="1" constant="true"/></listOfProducts>
        <fbc:geneProductAssociation>
          <fbc:and>
            <fbc:geneProductRef fbc:geneProduct="g1"/>
            <fbc:geneProductRef fbc:geneProduct="g2"/>
          </fbc:and>
        </fbc:geneProductAssociation>
      </reaction>
      <reaction id="R_BIOMASS" reversible="false" fbc:lowerFluxBound="cobra_0_bound" fbc:upperFluxBound="cobra_default_ub">
        <listOfReactants><speciesReference species="C" stoichiometry="1" constant="true"/></listOfReactants>
      </reaction>
    </listOfReactions>
    <fbc:listOfGeneProducts>
      <fbc:geneProduct fbc:id="g1" fbc:label="g1"/>
      <fbc:geneProduct fbc:id="g2" fbc:label="g2"/>
    </fbc:listOfGeneProducts>
    <fbc:listOfFluxObjectives>
      <fbc:fluxObjective fbc:reaction="R_BIOMASS" fbc:coefficient="1"/>
    </fbc:listOfFluxObjectives>
  </model>
</sbml>
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def make_model(tmp_path, text=MODEL):
    path = tmp_path / "model.xml"
    path.write_text(text, encoding="utf-8")
    return FileArtifact("sbml", {"model": str(path)})


def run(step, artifact, params):
    ctx = Ctx(params)
    step.run(ctx, [artifact])
    return ctx


def test_parse_sbml_bounds_and_gpr(tmp_path):
    artifact = make_model(tmp_path)
    parsed = parse_sbml(next(iter(artifact.files.values())))
    assert len(parsed["species"]) == 3
    assert len(parsed["reactions"]) == 4
    assert parsed["objective"] == "R_BIOMASS"
    bounds = {reaction["id"]: (reaction["lower"], reaction["upper"]) for reaction in parsed["reactions"]}
    assert bounds["R_EX"] == (0.0, 10.0)
    assert bounds["R1"] == (0.0, 1000.0)


def test_flux_distribution_growth(tmp_path):
    ctx = run(FbaFluxDistributionStep(), make_model(tmp_path), {"output": "flux"})
    form = ctx["flux"]
    assert form.info["growth_rate"] == pytest.approx(10.0)
    assert form.info["n_reactions"] == 4
    reaction = {name: index for name, index in form.labels["reaction"].items()}
    flux = {name: float(form.data[index, 0]) for name, index in reaction.items()}
    assert flux["R_EX"] == pytest.approx(10.0)
    assert flux["R1"] == pytest.approx(10.0)
    assert flux["R_BIOMASS"] == pytest.approx(10.0)


def test_gene_knockout_marks_essential(tmp_path):
    ctx = run(FbaGeneKnockoutStep(), make_model(tmp_path), {"output": "knockout", "max_genes": 0})
    form = ctx["knockout"]
    assert form.info["reference_growth"] == pytest.approx(10.0)
    assert form.info["n_genes"] == 2
    assert form.info["n_essential"] == 2
    for name, index in form.labels["gene"].items():
        assert float(form.data[index, 0]) == pytest.approx(0.0)
        assert float(form.data[index, 1]) == pytest.approx(0.0)
        assert float(form.data[index, 2]) == pytest.approx(1.0)


def test_fva_ranges(tmp_path):
    ctx = run(FbaFluxVariabilityStep(), make_model(tmp_path), {"output": "fva", "fraction_of_maximum": 0.9})
    form = ctx["fva"]
    index = form.labels["reaction"]["R_EX"]
    assert float(form.data[index, 0]) == pytest.approx(9.0, abs=1e-9)
    assert float(form.data[index, 1]) == pytest.approx(10.0, abs=1e-9)
    assert float(form.data[index, 2]) == pytest.approx(1.0, abs=1e-9)
    assert form.info["growth_rate"] == pytest.approx(10.0)
    assert form.info["n_blocked"] == 0


def test_wrong_artifact_format(tmp_path):
    path = tmp_path / "x.fasta"
    path.write_text(">a\nACGT\n", encoding="utf-8")
    with pytest.raises(StepError, match="expected an SBML model"):
        run(FbaFluxDistributionStep(), FileArtifact("fasta", {"seq": str(path)}), {})


def test_malformed_sbml(tmp_path):
    artifact = make_model(tmp_path, text="<sbml><model></sbml>")
    with pytest.raises(StepError, match="cannot read SBML model"):
        run(FbaFluxDistributionStep(), artifact, {})
