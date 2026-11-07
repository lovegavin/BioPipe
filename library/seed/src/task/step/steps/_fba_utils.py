"""Parse an SBML (FBC2) metabolic model and solve flux balance problems."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import numpy as np

from src.core.errors import StepError

S = "http://www.sbml.org/sbml/level3/version1/core"
F = "http://www.sbml.org/sbml/level3/version1/fbc/version2"
NS = {"s": S, "f": F}


def _tag(element):
    return element.tag.split("}")[-1]


def _gpr_node(element):
    tag = _tag(element)
    if tag == "geneProductRef":
        return ("gene", element.get(f"{{{F}}}geneProduct") or element.get("geneProduct"))
    children = [_gpr_node(child) for child in element]
    if not children:
        return None
    if tag in ("or", "and"):
        return (tag, children)
    if len(children) == 1:
        return children[0]
    return ("and", children)


def _evaluate(node, active):
    if node is None:
        return True
    kind = node[0]
    if kind == "gene":
        return node[1] in active
    if kind == "or":
        return any(_evaluate(child, active) for child in node[1])
    return all(_evaluate(child, active) for child in node[1])


def sbml_path(artifact, operator):
    if getattr(artifact, "format", "") != "sbml":
        raise StepError(f"{operator}: expected an SBML model")
    artifact.validate()
    return next(iter(artifact.files.values()))


def parse_sbml(path):
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise StepError(f"fba: cannot read SBML model: {exc}") from exc
    model = root.find("s:model", NS)
    if model is None:
        raise StepError("fba: SBML file has no model element")

    parameters = {}
    for node in model.iter(f"{{{S}}}parameter"):
        raw = node.get(f"{{{F}}}value") or node.get("value")
        if node.get("id") and raw is not None:
            parameters[node.get("id")] = float(raw)

    species = [entry.get("id") for entry in model.findall("s:listOfSpecies/s:species", NS)]
    if not species:
        raise StepError("fba: model has no species")
    reactions = []
    for entry in model.findall("s:listOfReactions/s:reaction", NS):
        rid = entry.get("id")
        if not rid:
            continue
        lower = parameters.get(entry.get(f"{{{F}}}lowerFluxBound"), -1000.0)
        upper = parameters.get(entry.get(f"{{{F}}}upperFluxBound"), 1000.0)
        stoich = {}
        for side, sign in (("listOfReactants", -1.0), ("listOfProducts", 1.0)):
            for ref in entry.findall(f"s:{side}/s:speciesReference", NS):
                name = ref.get("species")
                amount = float(ref.get("stoichiometry", 1.0))
                stoich[name] = stoich.get(name, 0.0) + sign * amount
        association = entry.find("f:geneProductAssociation", NS)
        gpr = None
        if association is not None:
            for child in association:
                gpr = _gpr_node(child)
                break
        reactions.append({
            "id": rid,
            "name": entry.get("name") or rid,
            "lower": lower,
            "upper": upper,
            "stoichiometry": stoich,
            "gpr": gpr,
        })
    if not reactions:
        raise StepError("fba: model has no reactions")

    objective = None
    for node in model.iter(f"{{{F}}}fluxObjective"):
        objective = node.get(f"{{{F}}}reaction")
        break
    if objective is None:
        candidates = [r for r in reactions if "BIOMASS" in r["id"].upper()]
        if not candidates:
            raise StepError("fba: model has no objective reaction")
        objective = candidates[0]["id"]

    gene_ids = {}
    for entry in model.findall("f:listOfGeneProducts/f:geneProduct", NS):
        identifier = entry.get(f"{{{F}}}id") or entry.get("id")
        if not identifier:
            continue
        label = entry.get(f"{{{F}}}label") or entry.get("label") or identifier
        gene_ids[label] = identifier
    genes = list(gene_ids)
    return {
        "species": species,
        "reactions": reactions,
        "objective": objective,
        "genes": genes,
        "gene_ids": gene_ids,
        "parameters": parameters,
    }


def stoichiometric_matrix(model):
    index = {name: position for position, name in enumerate(model["species"])}
    matrix = np.zeros((len(model["species"]), len(model["reactions"])))
    for column, reaction in enumerate(model["reactions"]):
        for name, coefficient in reaction["stoichiometry"].items():
            if name in index:
                matrix[index[name], column] += coefficient
    return matrix


def objective_vector(model):
    vector = np.zeros(len(model["reactions"]))
    for position, reaction in enumerate(model["reactions"]):
        if reaction["id"] == model["objective"]:
            vector[position] = 1.0
    if not np.any(vector):
        raise StepError(f"fba: objective reaction {model['objective']} is missing")
    return vector


def solve(model, bounds=None, extra_rows=None, weights=None):
    """Maximise ``weights @ v`` (default: the model objective) and return (value, v)."""
    from scipy.optimize import linprog

    matrix = stoichiometric_matrix(model)
    objective = objective_vector(model) if weights is None else np.asarray(weights, dtype=float)
    if objective.shape != (len(model["reactions"]),):
        raise StepError("fba: objective vector has the wrong length")
    if bounds is None:
        bounds = [(r["lower"], r["upper"]) for r in model["reactions"]]
    a_ub = None
    b_ub = None
    if extra_rows:
        a_ub = np.vstack([row for row, _ in extra_rows])
        b_ub = np.array([value for _, value in extra_rows])
    result = linprog(
        c=-objective,
        A_eq=matrix,
        b_eq=np.zeros(matrix.shape[0]),
        A_ub=a_ub,
        b_ub=b_ub,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        raise StepError(f"fba: linear program failed: {result.message}")
    return -float(result.fun), np.asarray(result.x, dtype=float)


def gene_bounds(model, gene):
    identifier = model.get("gene_ids", {}).get(gene, gene)
    active = set(model.get("gene_ids", {}).values()) - {identifier}
    bounds = []
    for reaction in model["reactions"]:
        if reaction["gpr"] is not None and not _evaluate(reaction["gpr"], active):
            bounds.append((0.0, 0.0))
        else:
            bounds.append((reaction["lower"], reaction["upper"]))
    return bounds


def gene_growth(model, gene, reference=None):
    try:
        growth, _ = solve(model, bounds=gene_bounds(model, gene))
    except StepError as exc:
        if "infeasible" not in str(exc).lower():
            raise
        growth = 0.0
    if reference is None:
        reference, _ = solve(model)
    ratio = growth / reference if reference > 0 else 0.0
    return growth, ratio


def flux_variability(model, fraction=0.9, tolerance=1e-9):
    growth, _ = solve(model)
    if growth <= 0:
        raise StepError("fba: model cannot grow under the current bounds")
    objective = objective_vector(model)
    rows = [(-objective, -fraction * growth)]
    values = []
    for position in range(len(model["reactions"])):
        unit = np.zeros(len(model["reactions"]))
        unit[position] = 1.0
        _, low_flux = solve(model, extra_rows=rows, weights=-unit)
        _, high_flux = solve(model, extra_rows=rows, weights=unit)
        values.append((float(low_flux[position]), float(high_flux[position])))
    return growth, values
