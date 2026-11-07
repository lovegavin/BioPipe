"""Helpers for RNA secondary-structure comparison, features and consensus."""

from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which

from src.core.errors import StepError

_BASES = set("ACGU")
_OPEN = "([{<"
_CLOSE = ")]}>"


def clean_rna(sequence: str, operator: str) -> str:
    text = "".join(str(sequence).split()).upper().replace("T", "U")
    if not text:
        raise StepError(f"{operator}: the sequence is empty")
    invalid = sorted({char for char in text if char not in _BASES | {"N"}})
    if invalid:
        raise StepError(f"{operator}: sequence contains non-nucleotide characters {invalid}")
    return text


def _resolve(binary: str, operator: str) -> str:
    resolved = binary if Path(str(binary)).is_file() else which(str(binary))
    if not resolved:
        raise StepError(f"{operator}: '{binary}' was not found on PATH")
    return str(resolved)


def _canonical(text: str, operator: str) -> str:
    chars = []
    for char in text.strip():
        if char == ".":
            chars.append(".")
        elif char in _OPEN:
            chars.append("(")
        elif char in _CLOSE:
            chars.append(")")
        else:
            raise StepError(f"{operator}: structure contains invalid character {char!r}")
    depth = 0
    for char in chars:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise StepError(f"{operator}: structure has more closing than opening brackets")
    if depth:
        raise StepError(f"{operator}: structure has unclosed brackets")
    return "".join(chars)


def fold_structures(
    sequences: list[str],
    *,
    binary: str = "RNAfold",
    temperature: float = 37.0,
    dangles: int = 2,
    timeout: int = 600,
) -> list[str]:
    operator = "rna_structure_fold"
    resolved = _resolve(binary, operator)
    command = [resolved, "--noPS", "-T", f"{float(temperature):.1f}", "-d", str(int(dangles))]
    completed = subprocess.run(
        command,
        input="".join(f">{index}\n{sequence}\n" for index, sequence in enumerate(sequences)),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-2:]
        raise StepError(f"{operator}: RNAfold failed with exit code {completed.returncode}: {' | '.join(tail)}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    structures: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].startswith(">"):
            if index + 2 >= len(lines) - 0:
                break
            structure = lines[index + 2].split()[0]
            structures.append(_canonical(structure, operator))
            index += 3
        else:
            index += 1
    if len(structures) != len(sequences):
        raise StepError(f"{operator}: parsed {len(structures)} structures for {len(sequences)} sequences")
    return structures


def subopt_structures(
    sequences: list[str],
    *,
    binary: str = "RNAsubopt",
    temperature: float = 37.0,
    energy_window: float = 3.0,
    max_structures: int = 20,
    timeout: int = 600,
) -> list[list[str]]:
    operator = "rna_structure_consensus"
    resolved = _resolve(binary, operator)
    command = [
        resolved,
        "-s",
        "-e",
        f"{float(energy_window):.2f}",
        "-T",
        f"{float(temperature):.1f}",
    ]
    completed = subprocess.run(
        command,
        input="".join(f">{index}\n{sequence}\n" for index, sequence in enumerate(sequences)),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-2:]
        raise StepError(f"{operator}: RNAsubopt failed with exit code {completed.returncode}: {' | '.join(tail)}")
    groups: list[list[str]] = []
    current: list[str] | None = None
    for line in completed.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith(">"):
            current = []
            groups.append(current)
            continue
        if current is None:
            continue
        structure = text.split()[0]
        if set(structure) <= set(".()[]{}<>"):
            if len(current) < int(max_structures):
                current.append(_canonical(structure, operator))
    if len(groups) != len(sequences):
        raise StepError(f"{operator}: parsed {len(groups)} suboptimal ensembles for {len(sequences)} sequences")
    if any(len(group) < 2 for group in groups):
        raise StepError(f"{operator}: a sequence produced fewer than two suboptimal structures")
    return groups


def pair_table(structure: str, operator: str = "rna_structure") -> list[int]:
    partners = [-1] * len(structure)
    stack: list[int] = []
    for index, char in enumerate(structure):
        if char == "(":
            stack.append(index)
        elif char == ")":
            if not stack:
                raise StepError(f"{operator}: unbalanced structure")
            start = stack.pop()
            partners[start] = index
            partners[index] = start
    if stack:
        raise StepError(f"{operator}: unbalanced structure")
    return partners


def pairs_of(structure: str, operator: str = "rna_structure") -> list[tuple[int, int]]:
    partners = pair_table(structure, operator)
    return [(i, j) for i, j in enumerate(partners) if j > i]


def base_pair_distance(left: str, right: str, operator: str) -> int:
    if len(left) != len(right):
        raise StepError(f"{operator}: structures must have the same length ({len(left)} != {len(right)})")
    a = set(pairs_of(left, operator))
    b = set(pairs_of(right, operator))
    return len(a ^ b)


def hamming_distance(left: str, right: str, operator: str) -> int:
    if len(left) != len(right):
        raise StepError(f"{operator}: structures must have the same length ({len(left)} != {len(right)})")
    return sum(1 for a, b in zip(left, right) if a != b)


def structure_features(structure: str, operator: str = "rna_structure") -> dict[str, float]:
    pair_table(structure, operator)
    children: dict[tuple[int, int], list[tuple[int, int]]] = {
        pair: [] for pair in pairs_of(structure, operator)
    }
    pairs = list(children)
    for i, j in pairs:
        for k, l in pairs:
            if i < k and l < j:
                nested = any(i < a < k and l < b < j for a, b in pairs)
                if not nested:
                    children[(i, j)].append((k, l))
    hairpins = bulges = internal = multiloops = stacked = 0
    for pair, kids in children.items():
        i, j = pair
        if not kids:
            hairpins += 1
            continue
        if len(kids) >= 2:
            multiloops += 1
            continue
        k, l = kids[0]
        left = k - i - 1
        right = j - l - 1
        if left == 0 and right == 0:
            stacked += 1
        elif (left == 0) != (right == 0):
            bulges += 1
        else:
            internal += 1
    parents: dict[tuple[int, int], tuple[int, int]] = {}
    for parent, kids in children.items():
        for kid in kids:
            parents[kid] = parent
    stems = [pair for pair in children if pair not in parents]
    max_stem = 0
    for pair in stems:
        length = 1
        current = pair
        while True:
            nxt = [kid for kid in children.get(current, []) if kid == (current[0] + 1, current[1] - 1)]
            if not nxt:
                break
            length += 1
            current = nxt[0]
        max_stem = max(max_stem, length)
    return {
        "n_pairs": float(len(children)),
        "n_stems": float(len(stems)),
        "max_stem_length": float(max_stem),
        "n_hairpins": float(hairpins),
        "n_bulges": float(bulges),
        "n_internal_loops": float(internal),
        "n_multiloops": float(multiloops),
        "n_stacked_pairs": float(stacked),
        "n_unpaired": float(structure.count(".")),
    }


def pair_frequencies(structures: list[str], operator: str) -> dict[tuple[int, int], float]:
    if not structures:
        raise StepError(f"{operator}: no structures were supplied")
    length = len(structures[0])
    counts: dict[tuple[int, int], int] = {}
    for structure in structures:
        if len(structure) != length:
            raise StepError(f"{operator}: structures must have the same length")
        for pair in pairs_of(structure, operator):
            counts[pair] = counts.get(pair, 0) + 1
    return {pair: count / len(structures) for pair, count in counts.items()}


def consensus_structure(
    frequencies: dict[tuple[int, int], float],
    length: int,
    threshold: float,
    operator: str,
) -> tuple[str, list[tuple[int, int]]]:
    candidates = sorted(frequencies.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    accepted: list[tuple[int, int]] = []
    for (i, j), probability in candidates:
        if probability < threshold:
            break
        if any(k == i or k == j or l == i or l == j for k, l in accepted):
            continue
        if any((i < k < j < l) or (k < i < l < j) for k, l in accepted):
            continue
        accepted.append((i, j))
    text = ["."] * length
    for i, j in accepted:
        text[i] = "("
        text[j] = ")"
    return "".join(text), accepted
