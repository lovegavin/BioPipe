"""Shared helpers for Gene Ontology information-content operators."""

from __future__ import annotations

import gzip
import math
from typing import Dict, Iterable, List, Sequence, Set, Tuple

ASPECTS = {"P": "biological_process", "F": "molecular_function", "C": "cellular_component"}


def parse_obo(path: str) -> Dict[str, dict]:
    terms: Dict[str, dict] = {}
    current = None
    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line == "[Term]":
                current = {"id": None, "name": "", "namespace": "", "parents": set(), "alt": set(), "obsolete": False}
                continue
            if line.startswith("["):
                if current and current["id"]:
                    terms[current["id"]] = current
                current = None
                continue
            if current is None:
                continue
            if not line:
                if current["id"]:
                    terms[current["id"]] = current
                current = None
                continue
            if line.startswith("id: "):
                current["id"] = line[4:].strip()
            elif line.startswith("name: "):
                current["name"] = line[6:].strip()
            elif line.startswith("namespace: "):
                current["namespace"] = line[11:].strip()
            elif line.startswith("is_a: "):
                current["parents"].add(line[6:].split()[0])
            # is_a-only propagation, matching the usual GO semantic-similarity
            # convention (goatools, GOSemSim); part_of is not inherited here.
            elif line.startswith("alt_id: "):
                current["alt"].add(line[8:].strip())
            elif line.startswith("is_obsolete: true"):
                current["obsolete"] = True
    if current and current["id"]:
        terms[current["id"]] = current
    return terms


def alt_map(terms: Dict[str, dict]) -> Dict[str, str]:
    mapping = {}
    for primary, term in terms.items():
        for other in term["alt"]:
            mapping[other] = primary
    return mapping


def ancestors(term_id: str, terms: Dict[str, dict]) -> Set[str]:
    seen: Set[str] = set()
    stack = [term_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        term = terms.get(current)
        if not term:
            continue
        for parent in term["parents"]:
            if parent not in seen:
                stack.append(parent)
    return seen


def depth(term_id: str, terms: Dict[str, dict]) -> int:
    seen: Dict[str, int] = {}

    def walk(node: str, trail: Set[str]) -> int:
        if node in seen:
            return seen[node]
        if node in trail:
            return 0
        term = terms.get(node)
        if not term or not term["parents"]:
            seen[node] = 0
            return 0
        trail = trail | {node}
        value = 1 + max(walk(parent, trail) for parent in term["parents"])
        seen[node] = value
        return value

    return walk(term_id, set())


def read_gaf(path: str, aspect: str = "P", alias: Dict[str, str] | None = None, known: Dict[str, dict] | None = None) -> Tuple[Dict[str, Set[str]], int]:
    alias = alias or {}
    annotations: Dict[str, Set[str]] = {}
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("!"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9:
                continue
            if aspect != "all" and fields[8] != aspect:
                continue
            gene = fields[2] or fields[1]
            term_id = alias.get(fields[4], fields[4])
            if not term_id.startswith("GO:"):
                continue
            if known is not None:
                info = known.get(term_id)
                if info is None or info.get("obsolete"):
                    continue
            annotations.setdefault(gene, set()).add(term_id)
    annotations = {gene: terms for gene, terms in annotations.items() if terms}
    return annotations, len(annotations)


def expanded_counts(annotations: Dict[str, Set[str]], terms: Dict[str, dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for term_ids in annotations.values():
        union: Set[str] = set()
        for term_id in term_ids:
            union |= ancestors(term_id, terms)
        for term_id in union:
            counts[term_id] = counts.get(term_id, 0) + 1
    return counts


def information_content(counts: Dict[str, int], total: int) -> Dict[str, float]:
    if total <= 0:
        return {}
    return {term: -math.log2(count / total) for term, count in counts.items() if count > 0}


def term_similarity(term_a: str, term_b: str, terms: Dict[str, dict], ic: Dict[str, float]) -> dict:
    set_a = ancestors(term_a, terms)
    set_b = ancestors(term_b, terms)
    common = set_a & set_b
    if not common:
        return {"resnik": 0.0, "lin": 0.0, "jaccard": 0.0, "ic_a": ic.get(term_a, 0.0), "ic_b": ic.get(term_b, 0.0)}
    best = max(common, key=lambda term: ic.get(term, 0.0))
    resnik = ic.get(best, 0.0)
    ic_a = ic.get(term_a, 0.0)
    ic_b = ic.get(term_b, 0.0)
    lin = 0.0 if ic_a + ic_b <= 0 else 2.0 * resnik / (ic_a + ic_b)
    union = set_a | set_b
    jaccard = len(common) / len(union) if union else 0.0
    return {"resnik": resnik, "lin": lin, "jaccard": jaccard, "ic_a": ic_a, "ic_b": ic_b}


def gene_similarity(genes_a: Iterable[str], genes_b: Iterable[str], annotations: Dict[str, Set[str]], terms: Dict[str, dict], ic: Dict[str, float]) -> dict:
    set_a = annotations.get(genes_a, set()) if isinstance(genes_a, str) else set()
    set_b = annotations.get(genes_b, set()) if isinstance(genes_b, str) else set()
    if not set_a or not set_b:
        return {"best_match_average": 0.0, "max_similarity": 0.0, "shared_terms": 0}
    matrix = []
    for term_a in set_a:
        row = [term_similarity(term_a, term_b, terms, ic)["resnik"] for term_b in set_b]
        matrix.append(row)
    max_rows = [max(row) for row in matrix]
    max_cols = [max(matrix[i][j] for i in range(len(matrix))) for j in range(len(set_b))]
    bma = (sum(max_rows) / len(max_rows) + sum(max_cols) / len(max_cols)) / 2.0
    return {"best_match_average": bma, "max_similarity": max(max_rows), "shared_terms": len(set_a & set_b)}
