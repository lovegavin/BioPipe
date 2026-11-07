"""Read an SBML metabolic model as a file artifact."""
from src.reader.base import Reader


class SbmlFileReader(Reader):
    provider = "operon-readers"
    parameters_file = "sbml_file.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "SbmlFileReader",
        "version": "1.0.0",
        "kind": "reader",
        "title": "SbmlFileReader",
        "description": "Reference an SBML metabolic model without parsing it.",
        "category": "Data",
        "icon": "File",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "kind": "file",
                "numeric": False,
                "ndim": 0,
                "info": {"representation": {"type": "string", "const": "sbml"}},
                "info_open": True,
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "extensions": [".xml", ".sbml"],
        "handles_compression": False,
        "file_input": {"dims": ["file"], "labels": {}, "compression": []},
    }

    def read(self, path, dims, labels, **args):
        from src.reader.readers._sequencing import read_file_source

        return read_file_source(path, "sbml", **args)
