# src/datapipe/table.py
"""通用表格读取：CSV / TSV / Excel → Table"""

import pandas as pd

from src.datapipe.detect import detect_table_format
from src.datapipe.memory import Table


def read_table(path, id_col=None) -> Table:
    """
    id_col:
        None  -> 第一列作索引
        int   -> 指定列索引 (0-based) 作索引
        str   -> 指定列名作索引
    """
    fmt = detect_table_format(path)
    if fmt == "csv":
        df = pd.read_csv(path)
    elif fmt == "tsv":
        df = pd.read_csv(path, sep="\t")
    elif fmt == "excel":
        df = pd.read_excel(path, engine="openpyxl")
    else:
        raise ValueError(f"未知表格格式: {fmt}")

    if df.shape[1] < 1:
        raise ValueError(f"表格无数据列: {path}")

    if id_col is None:
        idx_name = df.columns[0]
    elif isinstance(id_col, int):
        idx_name = df.columns[id_col]
    elif isinstance(id_col, str):
        idx_name = id_col
    else:
        raise TypeError(f"id_col 类型不支持: {type(id_col)}")

    df = df.set_index(idx_name)
    df.index = df.index.astype(str)

    return Table(data=df, source_format=fmt)