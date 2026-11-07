"""PhyloXML tree reader."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(clade, *names: str) -> str | None:
    for tag in names:
        for child in clade:
            if _local(child.tag) == tag and child.text and child.text.strip():
                return child.text.strip()
    return None


class PhyloXmlReader(Reader):
    """Parse a PhyloXML phylogeny into a node x field table."""

    provider = 'operon-readers'
    parameters_file = 'phyloxml_reader.PhyloXmlReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'PhyloXmlReader',
        'version': '1.0.0',
        'kind': 'reader',
        'title': 'Parse a PhyloXML tree into a node x field table',
        'category': 'Data',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'version': 1,
                'numeric': True,
                'info': {'missing_code': {'type': ['number', 'null']},
                         'encoders': {'type': 'object', 'optional': True}},
                'dims': [],
                'labels': [],
                'parallel': [],
                'ndim': 2,
                'axis_fields': [],
                'info_open': False,
            },
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False},
        'description': 'Parse a PhyloXML tree into a node x field table.',
        'extensions': ['.phyloxml'],
        'requires_siblings': [],
        'excludes_siblings': [],
        'handles_compression': False,
        'file_input': {'dims': ['node', 'field'], 'labels': {'node': 'builtin', 'field': 'builtin'}},
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PhyloXML reader requires exactly two dims, got {dims}")
        node_dim, field_dim = dims
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise ReaderError(f"PhyloXML reader: invalid XML in {path.name}: {exc}") from exc

        phylogenies = [element for element in root.iter() if _local(element.tag) == "phylogeny"]
        if len(phylogenies) != 1:
            raise ReaderError(
                f"PhyloXML reader: expected exactly one phylogeny, found {len(phylogenies)}"
            )
        clades = [child for child in phylogenies[0] if _local(child.tag) == "clade"]
        if not clades:
            raise ReaderError("PhyloXML reader: the phylogeny has no clade")

        nodes: list[dict] = []
        _walk(clades[0], None, 0, nodes)
        if not nodes:
            raise ReaderError("PhyloXML reader: the phylogeny has no nodes")

        names = [node["name"] for node in nodes]
        parent_encoder = get_encoder("labelencoder")
        parent_codes = parent_encoder.fit_transform([node["parent"] for node in nodes])
        data = np.column_stack([
            parent_codes,
            [node["length"] for node in nodes],
            [node["depth"] for node in nodes],
            [1.0 if node["leaf"] else 0.0 for node in nodes],
        ])
        return Form(
            data=compact_numeric(data),
            dims=[node_dim, field_dim],
            labels={
                node_dim: unique_labels(names, node_dim, "phyloxml"),
                field_dim: unique_labels(
                    ["parent", "branch_length", "depth", "is_leaf"], field_dim, "phyloxml"
                ),
            },
            info={"missing_code": np.nan, "encoders": {field_dim: {"parent": parent_encoder}}},
        )


def _walk(clade, parent_name: str | None, depth: int, nodes: list[dict]) -> str:
    children = [child for child in clade if _local(child.tag) == "clade"]
    name = _child_text(clade, "name")
    if name is None:
        name = _child_text(clade, "scientific_name")
    if name is None:
        if not children:
            raise ReaderError("PhyloXML reader: a tip clade has no name")
        name = f"Internal{len(nodes)}"

    length = np.nan
    raw_length = clade.get("branch_length")
    if raw_length is None:
        raw_length = _child_text(clade, "branch_length")
    if raw_length is not None:
        try:
            length = float(raw_length)
        except ValueError as exc:
            raise ReaderError(
                f"PhyloXML reader: invalid branch_length {raw_length!r} on {name!r}"
            ) from exc
    nodes.append({"name": name, "parent": parent_name, "length": length,
                  "depth": depth, "leaf": not children})
    for child in children:
        _walk(child, name, depth + 1, nodes)
    return name
