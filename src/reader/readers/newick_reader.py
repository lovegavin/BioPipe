"""Newick tree reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


class NewickReader(Reader):
    """Parse a Newick tree into a node x field table."""

    output_contract = reader_contract()
    file_input = {"dims": ["node", "field"], "labels": {"node": "builtin", "field": "builtin"}}
    extensions = [".nwk", ".newick", ".tree"]
    handles_compression = False
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"Newick reader requires exactly two dims, got {dims}")
        node_dim, field_dim = dims
        text = path.read_text(encoding="utf-8")
        nodes = _parse_newick(text)
        names = [n["name"] for n in nodes]
        parent_enc = get_encoder("labelencoder")
        parent_codes = parent_enc.fit_transform([n["parent"] for n in nodes])
        data = np.column_stack([
            parent_codes,
            [n["length"] for n in nodes],
            [n["depth"] for n in nodes],
            [1.0 if n["leaf"] else 0.0 for n in nodes],
        ])
        return Form(
            data=compact_numeric(data),
            dims=[node_dim, field_dim],
            labels={
                node_dim: unique_labels(names, node_dim, "newick"),
                field_dim: unique_labels(["parent", "branch_length", "depth", "is_leaf"], field_dim, "newick"),
            },
            info={"missing_code": np.nan, "encoders": {field_dim: {"parent": parent_enc}}},
        )


class _Parser:
    def __init__(self, text: str):
        self.tokens = _tokenize(text)
        self.i = 0
        self.nodes = []

    def parse(self):
        self._subtree(None, 0)
        return self.nodes

    def _subtree(self, parent, depth):
        if self.i >= len(self.tokens):
            raise ReaderError("Newick reader: unexpected end of tree")
        token = self.tokens[self.i]
        if token == "(":
            self.i += 1
            children = []
            while True:
                children.append(self._subtree(None, depth + 1))
                if self.i >= len(self.tokens):
                    raise ReaderError("Newick reader: unterminated group")
                if self.tokens[self.i] == ",":
                    self.i += 1
                    continue
                if self.tokens[self.i] == ")":
                    self.i += 1
                    break
                raise ReaderError(f"Newick reader: expected ',' or ')', got {self.tokens[self.i]!r}")
            name = self._node_name() if self.i < len(self.tokens) and self.tokens[self.i] not in (":", ",", ")", ";") else f"Internal{len(self.nodes)}"
            idx = len(self.nodes)
            self.nodes.append({"name": name, "parent": parent, "length": np.nan, "depth": depth, "leaf": False})
            for child in children:
                child["parent"] = name
            self._length(idx)
            return self.nodes[idx]
        name = token
        self.i += 1
        if name in (",", ")", ";", ":"):
            raise ReaderError(f"Newick reader: unexpected token {name!r}")
        idx = len(self.nodes)
        node = {"name": name, "parent": parent, "length": np.nan, "depth": depth, "leaf": True}
        self.nodes.append(node)
        self._length(idx)
        return node

    def _node_name(self):
        if self.i < len(self.tokens) and self.tokens[self.i] not in ("(", ")", ",", ":", ";"):
            value = self.tokens[self.i]
            self.i += 1
            return value
        return f"Internal{len(self.nodes)}"

    def _length(self, idx):
        if self.i < len(self.tokens) and self.tokens[self.i] == ":":
            self.i += 1
            if self.i >= len(self.tokens):
                raise ReaderError("Newick reader: missing branch length")
            try:
                self.nodes[idx]["length"] = float(self.tokens[self.i])
            except ValueError as exc:
                raise ReaderError(f"Newick reader: invalid branch length {self.tokens[self.i]!r}") from exc
            self.i += 1


def _tokenize(text: str):
    import re
    return re.findall(r"[(),:;]|[^\s(),:;]+", text)


def _parse_newick(text: str):
    parser = _Parser(text)
    nodes = parser.parse()
    if not nodes:
        raise ReaderError("Newick reader: empty tree")
    return nodes
