"""K-mer enrichment of query sequences against a background set.

Every k-mer in the query set is compared with the background set by a two-sided
Fisher exact test; the log2 enrichment uses add-``pseudocount`` frequencies and
the p-values can be corrected with Benjamini-Hochberg.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.stats import fisher_exact

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_STATISTICS = ("query_count", "background_count", "log2_enrichment", "p_value", "q_value")


def kmer_counts(sequences: list[str], k: int) -> tuple[Counter, int]:
    """Count every length-``k`` window across the sequences."""

    counts: Counter = Counter()
    total = 0
    for sequence in sequences:
        sequence = sequence.upper()
        if len(sequence) < k:
            raise StepError(
                f"sequence_kmer_enrichment: sequence {sequence!r} is shorter than the k-mer size {k}"
            )
        for start in range(len(sequence) - k + 1):
            counts[sequence[start : start + k]] += 1
            total += 1
    return counts, total


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted q-values, monotone from the largest rank."""

    count = len(pvalues)
    if count == 0:
        return []
    order = np.argsort(np.asarray(pvalues, dtype=np.float64))
    adjusted = np.empty(count, dtype=np.float64)
    previous = 1.0
    for rank in range(count - 1, -1, -1):
        index = int(order[rank])
        value = float(pvalues[index]) * count / (rank + 1)
        value = min(previous, value, 1.0)
        adjusted[index] = value
        previous = value
    return adjusted.tolist()


def enrichment_rows(
    query: Counter,
    background: Counter,
    query_total: int,
    background_total: int,
    *,
    pseudocount: float = 0.5,
    correction: str = "bh",
    min_count: int = 1,
) -> list[dict]:
    """Per-k-mer counts, log2 enrichment and Fisher p/q values."""

    kmers = sorted(
        kmer for kmer in set(query) | set(background) if query.get(kmer, 0) >= min_count
    )
    if not kmers:
        raise StepError(
            "sequence_kmer_enrichment: no k-mer reaches min_count in the query set"
        )
    vocabulary = len(set(query) | set(background))
    rows: list[dict] = []
    for kmer in kmers:
        q = int(query.get(kmer, 0))
        b = int(background.get(kmer, 0))
        q_frequency = (q + pseudocount) / (query_total + pseudocount * vocabulary)
        b_frequency = (b + pseudocount) / (background_total + pseudocount * vocabulary)
        odds, p_value = fisher_exact([[q, query_total - q], [b, background_total - b]])
        rows.append(
            {
                "kmer": kmer,
                "query_count": q,
                "background_count": b,
                "log2_enrichment": float(np.log2(q_frequency / b_frequency)),
                "p_value": float(p_value),
            }
        )
    if correction == "bh":
        q_values = benjamini_hochberg([row["p_value"] for row in rows])
    else:
        q_values = [row["p_value"] for row in rows]
    for row, q_value in zip(rows, q_values):
        row["q_value"] = q_value
    rows.sort(key=lambda row: (-row["log2_enrichment"], row["kmer"]))
    return rows


class SequenceKmerEnrichmentStep(Step):
    """K-mer log-odds enrichment of query sequences against a background."""

    provider = "operon-core"

    parameters_file = "sequence_kmer_enrichment.SequenceKmerEnrichmentStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_kmer_enrichment",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Sequence k-mer enrichment",
        "description": (
            "Compare the k-mer content of query sequences to a background set: counts, add-"
            "pseudocount log2 enrichment, two-sided Fisher exact p-values and optional "
            "Benjamini-Hochberg q-values."
        ),
        "category": "Sequence",
        "icon": "ChartScatter",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                },
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        query_form, background_form = inputs
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        k = int(params.get("k") if params.get("k") is not None else 3)
        pseudocount = float(
            params.get("pseudocount") if params.get("pseudocount") is not None else 0.5
        )
        correction = str(params.get("correction") or "bh")
        min_count = int(params.get("min_count") if params.get("min_count") is not None else 1)
        kmer_dim = str(params.get("kmer_dim") or "kmer")
        out_name = str(params.get("output") or "enrichment")

        if not 2 <= k <= 8:
            raise StepError("sequence_kmer_enrichment: k must be between 2 and 8")
        if pseudocount < 0:
            raise StepError("sequence_kmer_enrichment: pseudocount must be non-negative")
        if correction not in {"bh", "none"}:
            raise StepError("sequence_kmer_enrichment: correction must be 'bh' or 'none'")
        if min_count < 1:
            raise StepError("sequence_kmer_enrichment: min_count must be at least 1")

        query = decode_sequences(query_form, sequence_dim, position_dim)
        background = decode_sequences(background_form, sequence_dim, position_dim)
        if not query:
            raise StepError("sequence_kmer_enrichment: the query set carries no sequence")
        if not background:
            raise StepError("sequence_kmer_enrichment: the background set carries no sequence")

        query_counts, query_total = kmer_counts(query, k)
        background_counts, background_total = kmer_counts(background, k)
        rows = enrichment_rows(
            query_counts,
            background_counts,
            query_total,
            background_total,
            pseudocount=pseudocount,
            correction=correction,
            min_count=min_count,
        )
        data = np.asarray(
            [
                [
                    row["query_count"],
                    row["background_count"],
                    row["log2_enrichment"],
                    row["p_value"],
                    row["q_value"],
                ]
                for row in rows
            ],
            dtype=np.float32,
        ).reshape(len(rows), len(_STATISTICS))
        out = Form(
            data=data,
            dims=[kmer_dim, "statistic"],
            labels={
                kmer_dim: {row["kmer"]: index for index, row in enumerate(rows)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "k": k,
                "n_kmers": len(rows),
                "query_windows": query_total,
                "background_windows": background_total,
                "correction": correction,
                "pseudocount": pseudocount,
                "n_significant": int(sum(1 for row in rows if row["q_value"] <= 0.05)),
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_kmers": len(rows),
            "k": k,
            "n_significant": out.info["n_significant"],
            "query_windows": query_total,
            "background_windows": background_total,
        }
        print(
            f"[sequence_kmer_enrichment] {len(rows)} {k}-mers, "
            f"{out.info['n_significant']} significant at q<=0.05"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
