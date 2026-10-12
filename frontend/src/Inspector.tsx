import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CaretDown,
  Cpu,
  FileArrowUp,
  HardDrives,
  Info,
  Trash,
  X,
} from "@phosphor-icons/react";
import { OperatorArtwork, OperatorPreview } from "./OperatorArtwork";
import { OperatorIcon } from "./icons";
import { api } from "./api";
import { displayTitle, inputCount, outputCount, specFor, retainedOutputs } from "./graph";
import type { Catalog, Graph, GraphNode, Parameter, RouteDefinition } from "./types";

function JsonField({
  label,
  value,
  onChange,
  disabled,
  allowArray = false,
}: {
  label: string;
  value: unknown;
  onChange: (value: Record<string, unknown>) => void;
  disabled: boolean;
  allowArray?: boolean;
}) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState("");
  useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setError("");
  }, [value]);
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        className="mono json-input"
        rows={5}
        disabled={disabled}
        value={text}
        spellCheck={false}
        onChange={(e) => {
          const raw = e.target.value;
          setText(raw);
          try {
            const next = JSON.parse(raw);
            if (!allowArray && (!next || Array.isArray(next) || typeof next !== "object"))
              throw Error("需要 JSON 对象");
            onChange(next);
            setError("");
          } catch {
            setError(allowArray ? "需要有效的 JSON 值" : "需要有效的 JSON 对象");
          }
        }}
      />
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}
function ParameterField({
  field,
  value,
  onChange,
  disabled,
}: {
  field: Parameter;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  const id = `param-${field.key}`;
  if (field.type === "json") return <JsonField label={field.label} value={value === undefined ? {} : value} disabled={disabled} onChange={onChange} allowArray/>;
  return (
    <label className="field" htmlFor={id}>
      <span>
        {field.label}
        {field.required && <small>必填</small>}
      </span>
      {field.type === "boolean" ? <input id={id} type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={e=>onChange(e.target.checked)}/> : field.type === "choice" ? (
        <select
          id={id}
          value={String(value ?? "")}
          disabled={disabled}
          onChange={(e) => onChange(field.options?.find(option => String(option) === e.target.value) ?? e.target.value)}
        >
          {!value && <option value="">请选择</option>}
          {field.options?.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ) : field.type === "integer" || field.type === "number" ? (
        <input
          id={id}
          type="number"
          min={field.min}
          max={field.max}
          step={field.step || (field.type === "integer" ? 1 : "any")}
          value={value === undefined ? "" : String(value)}
          disabled={disabled}
          onChange={(e) =>
            onChange(e.target.value === "" ? undefined : Number(e.target.value))
          }
        />
      ) : (
        <input
          id={id}
          value={
            field.type === "list"
              ? Array.isArray(value)
                ? value.join(", ")
                : ""
              : String(value ?? "")
          }
          disabled={disabled}
          placeholder={
            field.type === "list" ? "用逗号分隔，如 PC1, PC2" : undefined
          }
          onChange={(e) =>
            onChange(
              field.type === "list"
                ? e.target.value
                    .split(/[,，]/)
                    .map((v) => v.trim())
                    .filter(Boolean)
                : field.type === "scalar" && e.target.value.trim() !== "" && Number.isFinite(Number(e.target.value)) ? Number(e.target.value) : e.target.value,
            )
          }
        />
      )}
    </label>
  );
}
export function Inspector({
  graph,
  catalog,
  nodeId,
  settings,
  busy,
  uploadLimit,
  onNode,
  onMemory,
  onDelete,
  onError,
  onClose,
  onOpenRoute,
}: {
  graph: Graph;
  catalog: Catalog;
  nodeId: string | null;
  settings: boolean;
  busy: boolean;
  uploadLimit: number;
  onNode: (id: string, patch: Partial<GraphNode>) => void;
  onMemory: (value: Graph["memory"]) => void;
  onDelete: (id: string) => void;
  onError: (message: string) => void;
  onClose: () => void;
  onOpenRoute: (route: RouteDefinition) => void;
}) {
  const node = graph.nodes.find((n) => n.id === nodeId),
    spec = node ? specFor(node, catalog) : undefined;
  const fileInput = useRef<HTMLInputElement>(null);
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (content.current) content.current.scrollTop = 0;
  }, [node?.id, settings]);
  const [uploading, setUploading] = useState(false);
  const memory = graph.memory;
  const retainedNames = node ? retainedOutputs(node, spec) : [];
  function param(key: string, value: unknown) {
    if (!node) return;
    const next = { ...node.params };
    if (value === undefined) delete next[key];
    else next[key] = value;
    onNode(node.id, { params: next });
  }
  async function upload(file?: File) {
    if (!file || !node?.source) return;
    if (file.size > uploadLimit * 1024 ** 2)
      return onError(`文件超过 ${uploadLimit} MiB，可改用项目内路径。`);
    setUploading(true);
    try {
      const result = await api.upload(file);
      onNode(node.id, {
        source: { ...node.source, path: result.path },
        title: file.name.replace(/\.csv(?:\.gz)?$/i, ""),
      });
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  return (
    <aside
      className="inspector panel"
      aria-label={settings ? "执行设置" : "节点参数"}
    >
      <div className="panel-heading">
        <h2>{settings ? "执行设置" : "检查器"}</h2>
        <button
          className="icon-button mobile-close"
          title="关闭检查器"
          aria-label="关闭检查器"
          onClick={onClose}
        >
          <X size={17} />
        </button>
      </div>
      <div className="inspector-content" ref={content}>
        {settings ? (
          <>
            <div className="inspector-intro">
              <div className="node-icon">
                <HardDrives size={20} />
              </div>
              <h3>内存预算</h3>
              <p>先确定预算，再沿固定顺序执行。运行期间保留紧急溢写。</p>
            </div>
            <div className="field">
              <span>数据内存预算</span>
              <div className="segmented">
                <button
                  disabled={busy}
                  className={memory.budget_mb === undefined ? "active" : ""}
                  onClick={() => {
                    const next = { ...memory };
                    delete next.budget_mb;
                    onMemory(next);
                  }}
                >
                  自动
                </button>
                <button
                  disabled={busy}
                  className={memory.budget_mb !== undefined ? "active" : ""}
                  onClick={() => onMemory({ ...memory, budget_mb: 512 })}
                >
                  手动
                </button>
              </div>
            </div>
            {memory.budget_mb !== undefined ? (
              <label className="field">
                <span>
                  分配内存 <small>MiB</small>
                </span>
                <input
                  aria-label="分配内存 MiB"
                  type="number"
                  min="1"
                  step="1"
                  value={memory.budget_mb}
                  disabled={busy}
                  onChange={(e) =>
                    onMemory({ ...memory, budget_mb: Number(e.target.value) })
                  }
                />
              </label>
            ) : (
              <div className="note">
                <Info size={15} />
                <p>
                  运行前扫描一次，取可用内存的 25%，上限 2
                  GiB。检查与编辑不会扫描。
                </p>
              </div>
            )}
            <label className="toggle-field">
              <span>
                <strong>紧急溢写</strong>
                <small>触及固定压力阈值时，释放未锁定数据</small>
              </span>
              <input
                type="checkbox"
                checked={memory.auto_spill !== false}
                disabled={busy}
                onChange={(e) =>
                  onMemory({ ...memory, auto_spill: e.target.checked })
                }
              />
              <span className="toggle-track" />
            </label>
            <details className="advanced">
              <summary>
                高级预算 <CaretDown size={14} />
              </summary>
              {(["process_limit_mb", "disk_limit_mb"] as const).map((key) => (
                <label className="field" key={key}>
                  <span>
                    {key === "process_limit_mb"
                      ? "进程 RSS 阈值"
                      : "缓存磁盘上限"}
                    <small>MiB · 可选</small>
                  </span>
                  <input
                    type="number"
                    min={1}
                    placeholder="不设置"
                    value={memory[key] ?? ""}
                    disabled={busy}
                    onChange={(e) => {
                      const next = { ...memory };
                      if (e.target.value) next[key] = Number(e.target.value);
                      else delete next[key];
                      onMemory(next);
                    }}
                  />
                </label>
              ))}
              <p className="helper">
                RSS 包含 Python 和库的内存。数据预算只管理
                Form、元数据与估算的工作区。
              </p>
            </details>
            <div className="section-rule" />
            <div className="capability">
              <Cpu size={17} />
              <div>
                <strong>固定顺序 · CPU</strong>
                <p>支线按依赖排序后依次运行。分块由算子的实际能力决定。</p>
              </div>
            </div>
          </>
        ) : node ? (
          <>
            <div className="inspector-intro">
              <div className="node-icon">
                <OperatorArtwork spec={spec} source={node.kind === "source"}/>
              </div>
              <h3>{displayTitle(node, spec)}</h3>
              <p>
                {node.kind === "source"
                  ? "读取项目内文件，或上传 CSV 作为输入。"
                  : spec?.description}
              </p>
            </div>
            <OperatorPreview spec={spec}/>
            <label className="field">
              <span>显示名称</span>
              <input
                value={displayTitle(node, spec)}
                maxLength={120}
                disabled={busy}
                onChange={(e) => onNode(node.id, { title: e.target.value })}
              />
            </label>
            {node.kind === "source" && node.source ? (
              <>
                <input
                  ref={fileInput}
                  type="file"
                  accept=".csv,.gz"
                  className="sr-only"
                  aria-label="选择 CSV 文件"
                  onChange={(e) => void upload(e.target.files?.[0])}
                />
                <button
                  className="upload-button"
                  disabled={busy || uploading}
                  onClick={() => fileInput.current?.click()}
                >
                  <FileArrowUp size={22} />
                  <strong>{uploading ? "正在上传…" : "选择 CSV 文件"}</strong>
                  <small>CSV / CSV.gz · 上限 {uploadLimit} MiB</small>
                </button>
                <label className="field">
                  <span>项目内文件路径</span>
                  <textarea
                    rows={2}
                    value={node.source.path}
                    disabled={busy || uploading}
                    placeholder="例如 tasks/demo/input/data.csv"
                    onChange={(e) =>
                      onNode(node.id, {
                        source: { ...node.source!, path: e.target.value },
                      })
                    }
                  />
                </label>
                <label className="field">
                  <span>维度名称</span>
                  <input
                    value={node.source.dims.join(", ")}
                    disabled={busy}
                    onChange={(e) =>
                      onNode(node.id, {
                        source: {
                          ...node.source!,
                          dims: e.target.value
                            .split(/[,，]/)
                            .map((v) => v.trim())
                            .filter(Boolean),
                        },
                      })
                    }
                  />
                </label>
                <details className="advanced">
                  <summary>
                    标签与读取选项 <CaretDown size={14} />
                  </summary>
                  <JsonField
                    label="维度标签 JSON"
                    value={node.source.labels}
                    disabled={busy}
                    onChange={(labels) =>
                      onNode(node.id, { source: { ...node.source!, labels } })
                    }
                  />
                  <JsonField
                    label="Reader 参数 JSON"
                    value={node.source.args}
                    disabled={busy}
                    onChange={(args) =>
                      onNode(node.id, { source: { ...node.source!, args } })
                    }
                  />
                  <p className="helper">
                    CSV 默认第一行为列名。示例的 sample 标签自动生成，feature
                    标签来自表头。
                  </p>
                </details>
              </>
            ) : (
              <>
                {node.kind === "route" && node.route && <div className="route-inspector">
                  <span className="route-version">路线算子 · v{node.route.version}</span>
                  <p className="helper">参数保存在内部算子图中。当前画布保留这个版本的快照。</p>
                  <button className="subtle-button" onClick={() => onOpenRoute(node.route!)}><OperatorIcon name="Stack" size={17}/>打开路线的算子图</button>
                  <p className="helper">输入：{node.route.graph.interface?.inputs.map(p=>p.label).join(" / ") || "无"}</p>
                  <p className="helper">输出：{node.route.graph.interface?.outputs.map(p=>p.label).join(" / ") || "报告与图片"}</p>
                </div>}
                {node.kind !== "route" && <>
                <div className="section-caption">
                  参数 <span className="mono">{node.operator}</span>
                </div>
                {spec?.parameters.map((field) => (
                  <ParameterField
                    key={field.key}
                    field={field}
                    value={node.params[field.key]}
                    disabled={busy}
                    onChange={(value) => param(field.key, value)}
                  />
                ))}
                {spec?.output_parameter && (
                  <label className="field">
                    <span>输出数据名称</span>
                    <input
                      value={String(node.params.output ?? node.id)}
                      disabled={busy}
                      onChange={(e) => param("output", e.target.value)}
                    />
                  </label>
                )}
                {spec?.inputs_arity === "*" && (
                  <label className="field">
                    <span>输入端口数量</span>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={node.input_count}
                      disabled={busy}
                      onChange={(e) =>
                        onNode(node.id, {
                          input_count: Math.max(
                            1,
                            Math.min(20, Number(e.target.value)),
                          ),
                        })
                      }
                    />
                  </label>
                )}
                <details className="advanced">
                  <summary>
                    完整参数 JSON <CaretDown size={14} />
                  </summary>
                  <JsonField
                    label="算子参数"
                    value={node.params}
                    disabled={busy}
                    onChange={(params) => onNode(node.id, { params })}
                  />
                </details>
                </>}
                <div className="capability">
                  <Cpu size={16} />
                  <span>
                    CPU
                    {node.kind === "route" ? " · 共享外层内存规划" : spec?.memory_modes.includes("stream")
                      ? " · 支持分块"
                      : " · 整体处理"}
                  </span>
                </div>
              </>
            )}
            {retainedNames.map((name, index) => (
              <label className="check-field" key={name}>
                <input
                  type="checkbox"
                  checked={(memory.keep || []).includes(name)}
                  disabled={busy}
                  onChange={(e) => {
                    onMemory({
                      ...memory,
                      keep: e.target.checked
                        ? [...(memory.keep || []), name]
                        : (memory.keep || []).filter((k) => k !== name),
                    });
                  }}
                />
                <span>
                  {node.kind === "route" ? `额外保留 ${node.route?.graph.interface?.outputs[index]?.label || `输出 ${index + 1}`}` : retainedNames.length > 1
                    ? `保留 ${name}`
                    : "额外保留这份数据"}
                  <small>末端输出会自动保存，便于下载</small>
                </span>
              </label>
            ))}
            {inputCount(node, spec) > 0 && (
              <div className="connections">
                <div className="section-caption">输入连接</div>
                {Array.from({ length: inputCount(node, spec) }, (_, index) => {
                  const edge = graph.edges.find(
                    (e) =>
                      e.target === node.id && e.targetHandle === `in-${index}`,
                  );
                  const source = graph.nodes.find((n) => n.id === edge?.source);
                  return (
                    <div key={index}>
                      <span className="connection-number">{index + 1}</span>
                      <span>
                        {source
                          ? displayTitle(source, specFor(source, catalog))
                          : "尚未连接"}
                      </span>
                      <ArrowRight size={12} />
                    </div>
                  );
                })}
              </div>
            )}
            <div className="section-rule" />
            <button
              className="danger-text"
              disabled={busy}
              onClick={() => onDelete(node.id)}
            >
              <Trash size={15} />
              删除节点
            </button>
          </>
        ) : (
          <div className="inspector-empty">
            <OperatorIcon size={34} weight="light" />
            <h3>双击查看节点</h3>
            <p>
              单击选中，双击查看输入、参数与输出。也可以聚焦节点后按 Enter。
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
