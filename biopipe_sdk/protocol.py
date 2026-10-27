"""JSON-compatible public descriptors and parameter validation."""
import math
from copy import deepcopy
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL_VERSION = 1


class Descriptor(BaseModel):
    # Legacy UI fields are retained as extension fields in catalog v1.
    model_config = ConfigDict(extra="allow")
    protocol_version: Literal[1] = 1
    id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]{0,79}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
    kind: Literal["operator", "reader"]
    entry_point: str
    title: str
    category: str | None = Field(default=None, description="Operator library category, independent of package origin. Custom labels are allowed.")
    icon: str | None = Field(default=None, description="Optional module-relative image path or Studio icon name. Missing or unknown names use the category default.")
    icon_image: str | None = Field(default=None, pattern=r"^data:image/(png|jpeg|webp|gif|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$", description="SDK-generated portable image data; authors declare a relative path in icon.")
    parameters_schema: dict[str, Any]
    contracts: dict[str, Any]
    resources: dict[str, Any]
    dependencies: list[str] = Field(default_factory=list, description="PEP 508 dependencies; compatible versions share the host runtime, conflicting versions use a private dependency directory and subprocess with the same Python.")
    dependency_imports: list[str] = Field(default_factory=list, description="Optional import smoke checks, run outside the UI process.")

    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, value):
        from .dependencies import requirements
        return requirements(value)

    @field_validator('dependency_imports')
    @classmethod
    def validate_imports(cls, value):
        from .dependencies import imports
        return imports(value)


class PackageDescriptor(BaseModel):
    """One installation unit; operator identities remain independent of origin."""
    model_config = ConfigDict(extra="allow")
    protocol_version: Literal[1] = 1
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")
    version: str
    title: str | None = None
    origin: Literal["bundled", "wheel"] = "wheel"
    descriptors: list[Descriptor]


def validate_schema(schema):
    Draft202012Validator.check_schema(schema)
    if schema.get("type") != "object":
        raise ValueError("Parameter schema must describe an object")
    # Schemas are self-contained, so validation never fetches remote documents.
    def check(value):
        if isinstance(value, dict):
            for reference in ("$ref", "$dynamicRef"):
                if reference in value and not value[reference].startswith("#"):
                    raise ValueError("Only local JSON Schema references are supported")
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(schema)


def _normalize_numeric_strings(result, schema):
    """Accept YAML 1.1 strings such as ``1e6`` for declared numeric fields.

    YAML 1.1 parses an unquoted exponent without a decimal point as a
    string. Existing manifests use that spelling. The conversion is
    limited to fields the schema declares as number/integer, must be
    finite, and must be integral for integer-only fields.
    """
    for name, field in schema.get("properties", {}).items():
        if name not in result or not isinstance(result[name], str):
            continue
        types = field.get("type")
        types = types if isinstance(types, list) else [types]
        if "number" not in types and "integer" not in types:
            continue
        try:
            number = float(result[name])
        except ValueError:
            continue
        if not math.isfinite(number):
            continue
        if "number" not in types and not number.is_integer():
            continue
        result[name] = int(number) if number.is_integer() else number
    return result


def validate_parameters(schema, params):
    validate_schema(schema)
    result = _normalize_numeric_strings(deepcopy(params), schema)
    for name, field in schema.get("properties", {}).items():
        if name not in result and "default" in field:
            result[name] = deepcopy(field["default"])
    errors = sorted(Draft202012Validator(schema).iter_errors(result), key=lambda error: str(error.path))
    if errors:
        raise ValueError("; ".join(f"{'.'.join(map(str, e.path)) or 'params'}: {e.message}" for e in errors))
    return result


def schema_to_fields(schema):
    result = []
    for key, value in schema.get("properties", {}).items():
        kind = value.get("type", "object")
        if isinstance(kind, list):
            concrete = [item for item in kind if item != "null"]
            kind = value.get("x-ui-type", concrete[0] if len(concrete) == 1 else "object")
        field = {"key": key, "label": value.get("title", key),
                 "type": "choice" if "enum" in value else {"array": "json", "object": "json"}.get(kind, kind),
                 "required": key in schema.get("required", [])}
        if value.get("description"):
            field["description"] = value["description"]
        if value.get("type") == "array" and value.get("items", {}).get("type") == "string":
            field["type"] = "list"
        if not isinstance(field["type"], str):
            field["type"] = "json"
        for source, target in (("default", "default"), ("minimum", "min"), ("maximum", "max"), ("enum", "options")):
            if source in value:
                field[target] = deepcopy(value[source])
        result.append(field)
    return result


def legacy_schema(fields, defaults):
    properties = {}
    for field in fields:
        kind = field["type"]
        value = {"title": field.get("label", field["key"])}
        types = {"list": "array", "scalar": ["string", "number"], "json": ["object", "array"]}
        if kind == "choice":
            value["enum"] = field.get("options", [])
        else:
            value["type"] = types.get(kind, kind)
        for source, target in (("min", "minimum"), ("max", "maximum")):
            if source in field:
                value[target] = field[source]
        if field["key"] in defaults:
            value["default"] = defaults[field["key"]]
        properties[field["key"]] = value
    # Existing manifests can contain additional engine parameters. The adapter
    # advertises them without tightening historical validation behavior.
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "properties": properties, "additionalProperties": True,
            "required": [f["key"] for f in fields if f.get("required") and f["key"] not in defaults]}


_PARAM_TITLES = {
    "dim": "分析维度",
    "sample_dim": "样本维度",
    "feature_dim": "特征维度",
    "label_dim": "标签维度",
    "group_dim": "分组维度",
    "record_dim": "记录维度",
    "region_dim": "区间维度",
    "field_dim": "字段维度",
    "stat_dim": "统计维度",
    "dist_dim": "距离维度",
    "sequence_dim": "序列维度",
    "position_dim": "位置维度",
    "target_dim": "目标维度",
    "source_dim": "参考维度",
    "index_label": "行标签",
    "columns_label": "列标签",
    "values_label": "数值字段",
    "target_label": "目标字段",
    "group_label": "分组字段",
    "value_label": "数值字段",
    "other_label": "另一维度标签",
    "feature_type": "特征类型",
    "feature_id_field": "特征标识",
    "chrom_field": "染色体列",
    "start_field": "起始列",
    "end_field": "结束列",
    "type_field": "类型列",
    "attr_field": "属性列",
    "strand_field": "链方向列",
    "output": "输出名称",
    "method": "方法",
    "mode": "模式",
    "metric": "距离/相关指标",
    "metrics": "指标",
    "statistic": "统计量",
    "stats": "统计量",
    "threshold": "阈值",
    "min_value": "最小值",
    "max_value": "最大值",
    "min_samples": "最少样本数",
    "min_per_group": "每组最少样本",
    "min_overlap": "最小重叠",
    "min_gap": "最小间隙",
    "min_aa": "最短氨基酸",
    "min_valid": "最少有效值",
    "max_positions": "最大位置数",
    "max_output": "最大输出数",
    "max_distance": "最大距离",
    "top_n": "保留数量",
    "n_components": "主成分数",
    "n_clusters": "聚类数",
    "n_neighbors": "邻居数",
    "n_permutations": "置换次数",
    "n_estimators": "树数量",
    "n_iter": "迭代次数",
    "bins": "分箱数",
    "k": "k-mer 长度",
    "window_size": "窗口大小",
    "step_size": "步长",
    "resolution": "分辨率",
    "learning_rate": "学习率",
    "max_depth": "最大深度",
    "test_size": "测试集比例",
    "cv_folds": "交叉验证折数",
    "random_state": "随机种子",
    "scale": "标准化",
    "standardize": "标准化",
    "normalize": "归一化",
    "keep_ties": "保留并列",
    "descending": "降序",
    "pairwise": "两两比较",
    "groups": "分组顺序",
    "group_a": "A 组",
    "group_b": "B 组",
    "features": "特征列表",
    "genes": "基因列表",
    "motifs": "模体列表",
    "rules": "过滤规则",
    "columns": "列",
    "prefix": "前缀",
    "by": "排序依据",
    "filename": "图片文件名",
    "title": "图标题",
    "xlabel": "X 轴标题",
    "ylabel": "Y 轴标题",
    "cmap": "配色",
    "figsize": "图片尺寸",
    "legend": "显示图例",
    "legend_ncol": "图例列数",
    "rotate_labels": "旋转标签",
    "dot_scale": "点大小",
    "point_size": "点大小",
    "point_alpha": "点透明度",
    "show_points": "显示散点",
    "proportion_mode": "比例模式",
    "inner": "内部显示",
    "alpha": "显著性水平",
    "epsilon": "epsilon",
    "C": "正则强度 C",
    "penalty": "惩罚项",
    "class_weight": "类别权重",
    "valid_labels": "有效标签",
    "weights_label": "权重字段",
    "categorical": "分类协变量",
    "covariates": "协变量",
    "response": "响应变量",
    "time_label": "随访时间字段",
    "event_label": "事件字段",
    "pfield": "P 值字段",
    "p_label": "P 值字段",
    "lfc_label": "log2FC 字段",
    "hr_label": "HR 字段",
    "low_label": "下限字段",
    "high_label": "上限字段",
    "lfc_threshold": "log2FC 阈值",
    "p_threshold": "P 值阈值",
    "sort_by": "排序字段",
    "color_sig": "显著颜色",
    "color_ns": "不显著颜色",
    "log_scale": "对数坐标",
    "xlim": "X 轴范围",
    "label_top": "标注数量",
    "select": "选择方式",
    "labels": "标签",
    "nan_color": "缺失颜色",
    "cluster_rows": "聚类行",
    "cluster_cols": "聚类列",
    "show_row_labels": "显示行标签",
    "show_col_labels": "显示列标签",
    "other_dim": "另一维度",
    "how": "连接方式",
    "agg": "聚合方式",
    "group_col": "分组列",
    "index_name": "行轴名",
    "columns_name": "列轴名",
    "align": "对齐",
    "axis": "轴",
    "label": "标签",
    "fields": "字段",
    "field": "字段",
    "min_scale": "最小尺度",
    "target_sum": "目标总量",
    "base": "底数",
    "pseudocount": "伪计数",
}


def _default_title(key):
    if key in _PARAM_TITLES:
        return _PARAM_TITLES[key]
    for prefix, side in (("a_", "A："), ("b_", "B：")):
        if key.startswith(prefix):
            return side + _default_title(key[len(prefix):])
    return key.replace("_", " ").strip().title()


_ADVANCED_PARAMS = {
    "random_state", "test_size", "cv_folds", "n_estimators", "max_depth",
    "learning_rate", "n_iter", "perplexity", "n_neighbors", "min_dist",
    "metric", "penalty", "C", "epsilon", "alpha", "class_weight",
    "valid_labels", "cmap", "figsize", "legend", "legend_ncol",
    "point_size", "point_alpha", "rotate_labels", "show_points",
    "show_row_labels", "show_col_labels", "cluster_rows", "cluster_cols",
    "nan_color", "max_value", "min_scale", "prefix", "index_name",
    "columns_name", "agg", "how", "align", "field_dim", "stat_dim",
}


def normalize_schema_titles(schema):
    result = deepcopy(schema)
    for order, (key, field) in enumerate((result.get("properties") or {}).items()):
        if not isinstance(field, dict):
            continue
        if not field.get("title"):
            field["title"] = _default_title(key)
        field.setdefault("x-ui-group", "advanced" if key in _ADVANCED_PARAMS else "basic")
        field.setdefault("x-ui-order", order * 10)
        if key in {"window_size", "step_size", "min_gap", "max_distance"}:
            field.setdefault("x-ui-unit", "bp")
    return result


def describe_operator(cls, legacy=None):
    packaged = getattr(cls, "_package_descriptor", None)
    value = deepcopy(packaged or legacy or {})
    schema = getattr(cls, "parameters_schema", None)
    if schema is not None:
        validate_schema(schema)
        schema = normalize_schema_titles(schema)
        if not packaged:
            value["parameters"] = schema_to_fields(schema)
            value["runtime_defaults"] = {key: field["default"] for key, field in schema.get("properties", {}).items() if "default" in field}
    else:
        schema = legacy_schema(value.get("parameters", []), value.get("runtime_defaults", {}))
    output_parameter = getattr(cls, "output_parameter", None)
    value.update(protocol_version=1, id=cls.name, version=getattr(cls, "version", "1.0.0"), kind="operator",
                 entry_point=f"{cls.__module__}:{cls.__name__}", module=cls.__module__,
                 title=getattr(cls, "title", None) or value.get("title", cls.name),
                 parameters_schema=schema, name=cls.name, inputs_arity=cls.inputs_arity,
                 outputs=list(cls.outputs), output_parameter=output_parameter,
                 legacy_parameters=bool(getattr(cls, "legacy_parameters", False)),
                 contracts={"version": 1, "inputs": cls.input_contracts, "output": cls.output_contract},
                 resources={"memory_modes": ["full", "stream"] if cls.supports_streaming else ["full"],
                            "supports_cuda": bool(getattr(cls, "supports_cuda", False)),
                            "estimate": "estimate_memory",
                            **({"stream_protocol": cls.stream_protocol,
                                "stream_buffer_multiplier": cls.stream_buffer_multiplier,
                                "stream_fixed_bytes": cls.stream_fixed_bytes} if cls.supports_streaming else {})})
    # Declarations travel through source scans and wheel manifests alike. A base
    # class's None defaults must not erase older packaged presentation metadata.
    for field in ("category", "icon"):
        declared = getattr(cls, field, None)
        if declared is not None:
            value[field] = declared
    if value.get("category") is None:
        value["category"] = "Plugins"
    from biopipe_sdk.icons import resolve_icon
    resolve_icon(cls, value)
    from biopipe_sdk.dependencies import declarations
    value.update(declarations(cls, value))
    value.setdefault("description", (cls.__doc__ or "").strip())
    value.setdefault("input_type", "Form")
    value.setdefault("output_type", "Form" if cls.outputs or output_parameter else "Report")
    value.update(memory_modes=value["resources"]["memory_modes"], supports_cuda=value["resources"]["supports_cuda"])
    # Preserve the shape of previously built wheel manifests: optional display
    # fields that were never declared must not suddenly appear as null.
    return Descriptor.model_validate(value).model_dump(exclude_unset=True)


def describe_reader(reader):
    cls = type(reader)
    from biopipe_sdk.dependencies import declarations
    schema = getattr(cls, "parameters_schema", None) or {"type": "object", "additionalProperties": True}
    validate_schema(schema)
    schema = normalize_schema_titles(schema)
    return Descriptor(protocol_version=1, id=getattr(cls, "name", None) or cls.__name__,
                      version=getattr(cls, "version", "1.0.0"), kind="reader",
                      entry_point=f"{cls.__module__}:{cls.__name__}", title=getattr(cls, "title", None) or cls.__name__,
                      parameters_schema=schema, contracts={"version": 1, "inputs": [], "output": reader.output_contract},
                      parameters=schema_to_fields(schema),
                      resources={"memory_modes": ["full", "disk"] if reader.supports_disk_read else ["full"], "supports_cuda": False,
                                 **({"disk_protocol": reader.disk_protocol} if reader.supports_disk_read else {})},
                      name=cls.__name__, module=cls.__module__, extensions=list(reader.extensions),
                      requires_siblings=list(reader.requires_siblings), excludes_siblings=list(reader.excludes_siblings),
                      handles_compression=reader.handles_compression,
                      **({"file_input": deepcopy(reader.file_input)} if reader.file_input is not None else {}),
                      output_contract=reader.output_contract, **declarations(cls, getattr(cls, '_package_descriptor', None))).model_dump(exclude_unset=True)


def validate_output_rule(rule):
    modes = {"unknown", "declare", "project", "choose", "passthrough", "transform", "subset", "select", "drop", "rename", "transpose", "concat", "attach", "report", "none", "pca", "regress", "correction", "compare_groups", "cox_regression", "logrank_test"}
    if not isinstance(rule, dict) or rule.get("mode") not in modes:
        raise ValueError("Use a documented output contract mode")
    if rule["mode"] == "choose":
        if not isinstance(rule.get("param"), str) or not rule.get("cases"):
            raise ValueError("choose requires a parameter and non-empty cases")
        for case in rule["cases"].values():
            validate_output_rule(case)
        if "otherwise" in rule:
            validate_output_rule(rule["otherwise"])
    if rule["mode"] == "project":
        for axis in rule.get("prepend_dims", []) + rule.get("append_dims", []):
            if not isinstance(axis, dict) or not ("name" in axis or "input_axis" in axis):
                raise ValueError("Added dimensions require name or input_axis")
            ref = axis.get("input_axis")
            if ref is not None and (not isinstance(ref, list) or len(ref) != 2 or any(type(n) is not int or n < 0 for n in ref)):
                raise ValueError("input_axis must be [input_index, axis_index]")


def validate_port_rule(rule):
    if not isinstance(rule, dict):
        raise ValueError("Port contracts must be objects")
    if "numeric" in rule and not isinstance(rule["numeric"], bool):
        raise ValueError("Port numeric must be boolean")
    if rule.get("ndim") is not None and (type(rule["ndim"]) is not int or rule["ndim"] < 0):
        raise ValueError("Port ndim must be a nonnegative integer")
    if not isinstance(rule.get("info", {}), dict):
        raise ValueError("Port info must be an object")
    for key in ("dims", "labels", "parallel", "labels_any", "labels_axis"):
        value = rule.get(key, [])
        if not isinstance(value, list) and not (isinstance(value, dict) and isinstance(value.get("param"), str)):
            raise ValueError(f"Port {key} must be a list or parameter reference")


def validate_extension(cls, kind):
    """Strict authoring requirements for new extensions; legacy adapters stay permissive."""
    from src.task.step.base import Step
    from src.reader.base import Reader
    base = Step if kind == "operator" else Reader
    if not isinstance(cls, type) or not issubclass(cls, base):
        raise ValueError(f"Plugin entry must subclass {base.__name__}")
    if cls.parameters_schema is None:
        raise ValueError("Plugins must declare parameters_schema, including readers with no options")
    validate_schema(cls.parameters_schema)
    if not cls.output_contract:
        raise ValueError("Plugins must declare output_contract")
    if kind == "operator":
        if cls.output_parameter not in (None, "output"):
            raise ValueError("Plugin v1 supports only the dynamic output parameter 'output'")
        arity = cls.inputs_arity
        if arity != "*" and (type(arity) is not int or arity < 0 or arity > 20):
            raise ValueError("inputs_arity must be an integer from 0 to 20 or '*'")
        if cls.input_contracts is None or len(cls.input_contracts) != (1 if arity == "*" else arity):
            raise ValueError("Declare one input contract per port (one repeat contract for '*')")
        for contract in cls.input_contracts:
            validate_port_rule(contract)
        validate_output_rule(cls.output_contract)
        if cls.output_contract["mode"] not in {"report", "none", "unknown"} and not (cls.outputs or cls.output_parameter):
            raise ValueError("Form-producing operators must declare outputs or output_parameter")
        if cls.supports_streaming:
            if (cls.stream_protocol != "flat-reduction-v1" or cls.inputs_arity != 1
                    or cls.output_contract.get("mode") not in {"report", "none"}
                    or cls.outputs or cls.output_parameter or cls.run_stream is Step.run_stream):
                raise ValueError("Streaming requires flat-reduction-v1, one input, report-only output and run_stream")
            if (type(cls.stream_buffer_multiplier) is not int or cls.stream_buffer_multiplier < 1
                    or type(cls.stream_fixed_bytes) is not int or cls.stream_fixed_bytes < 0):
                raise ValueError("Stream buffer multiplier and fixed workspace must be valid integer estimates")
    else:
        validate_port_rule(cls.output_contract)
        if cls.supports_disk_read:
            if (cls.disk_protocol != "dense-writer-v1" or cls.probe is Reader.probe
                    or cls.read_to_disk is Reader.read_to_disk):
                raise ValueError("Disk readers require dense-writer-v1, probe and read_to_disk")
        if not cls.extensions or any(not isinstance(ext, str) or not ext.startswith(".") for ext in cls.extensions):
            raise ValueError("Readers must declare file extensions such as '.npy'")
