"""Arrow IPC, Feather and ORC reader.

Reads a two-dimensional columnar table with pyarrow. Arrow IPC files,
Feather files and ORC files share the same table layout, and column names
come from the file schema. The ``format`` parameter selects the container
explicitly; ``auto`` dispatches on the file extension.

Label rules follow the other table readers:

    builtin           column names from the file schema
    auto              position indices "0", "1", ...
    {<col_dim>: <k>}  read column <k>; its values become the row labels
                      and the column is removed from data
    {name: pos, ...}  explicit mapping

Non-numeric columns are encoded. The encoder instance used for each column
is recorded in ``info["encoders"]`` as ``{col_dim: {label: encoder}}``.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
"""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels
from src.reader.readers._table_common import table_form


class ArrowReader(Reader):
    """Reader for Arrow IPC, Feather and ORC tables."""

    provider = 'operon-readers'
    parameters_file = 'arrow_reader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
                  'id': 'ArrowReader',
                  'version': '1.0.0',
                  'kind': 'reader',
                  'title': 'Arrow, Feather and ORC table reader',
                  'category': 'Data',
                  'contracts': {'version': 1,
                                'inputs': [],
                                'output': {'version': 1,
                                           'numeric': True,
                                           'info': {'missing_code': {'type': ['number', 'null']},
                                                    'encoders': {'type': 'object',
                                                                 'optional': True}},
                                           'dims': [],
                                           'labels': [],
                                           'parallel': [],
                                           'ndim': 2,
                                           'axis_fields': [],
                                           'info_open': False}},
                  'resources': {'memory_modes': ['full'], 'supports_cuda': False},
                  'dependencies': ['pyarrow>=14'],
                  'dependency_imports': ['pyarrow'],
                  'extensions': ['.arrow', '.feather', '.ipc', '.orc'],
                  'requires_siblings': [],
                  'excludes_siblings': [],
                  'handles_compression': False,
                  'file_input': {'dims': ['sample', 'feature'],
                                 'labels': {'sample': 'auto',
                                            'feature': 'builtin'}},
                  'description': 'Reads Arrow IPC, Feather and ORC columnar tables with pyarrow.'}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"Arrow reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]
        table = _read_table(path, str(args.get("format", "auto")))
        try:
            df = table.to_pandas()
        except Exception as exc:
            raise ReaderError(
                f"Arrow reader: cannot convert {path.name} to a table: {exc}"
            ) from exc
        df.columns = [str(c) for c in df.columns]
        labels = dict(labels)
        row_labels = None
        rule = labels.get(row_dim)
        if isinstance(rule, dict) and set(rule) == {col_dim}:
            k = rule[col_dim]
            if not isinstance(k, int) or not 0 <= k < df.shape[1]:
                raise ReaderError(
                    f"Arrow reader: labels.{row_dim} column index {k!r} "
                    f"is out of range (file has {df.shape[1]} columns)"
                )
            row_labels = unique_labels(
                df.iloc[:, k].astype(str).tolist(), row_dim, "arrow"
            )
            df = df.drop(columns=[df.columns[k]])
            labels.pop(row_dim, None)
        return table_form(df, dims, labels, "Arrow", args.get("encoders", {}),
                          row_labels=row_labels)


def _read_table(path: Path, fmt: str):
    try:
        import pyarrow.feather as feather
    except ImportError as exc:
        raise ReaderError("Arrow reader requires pyarrow>=14") from exc
    suffix = path.suffix.lower()
    requested = (fmt or "auto").strip().lower()
    resolved = requested
    if resolved == "auto":
        resolved = {".orc": "orc", ".ipc": "ipc"}.get(suffix, "feather")
    if resolved not in {"feather", "ipc", "orc"}:
        raise ReaderError(
            f"Arrow reader: unknown format {fmt!r}; use auto, feather, ipc or orc"
        )
    try:
        if resolved == "orc":
            import pyarrow.orc as orc
            return orc.read_table(path)
        if resolved == "ipc":
            return _read_ipc(path)
        try:
            return feather.read_table(path)
        except Exception as exc:
            # Feather V2 is Arrow IPC, but a .arrow file can also be a raw
            # IPC stream; only the auto path is allowed to fall back.
            if requested != "auto" or suffix not in {".arrow", ".feather"}:
                raise
            try:
                return _read_ipc(path)
            except Exception:
                raise exc
    except ReaderError:
        raise
    except Exception as exc:
        raise ReaderError(f"Arrow reader: cannot read {path.name}: {exc}") from exc


def _read_ipc(path: Path):
    import pyarrow as pa
    import pyarrow.ipc as ipc
    try:
        return ipc.open_file(path).read_all()
    except pa.ArrowInvalid:
        return ipc.open_stream(path).read_all()
