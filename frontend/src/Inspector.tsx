import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CaretDown,
  Cpu,
  FileArrowUp,
  HardDrives,
  Trash,
  X,
} from "@phosphor-icons/react";
import { OperatorArtwork, OperatorPreview } from "./OperatorArtwork";
import { OperatorIcon } from "./icons";
import { HelpTip } from "./HelpTip";
import {ExecutionSettings} from './ExecutionSettings';
import {defaultTarget, executionConfig, groupParameters, nodeTarget, targetFromKey, targetKey, targetLabel} from './execution';
import { api } from "./api";
import { inputAccept, renameSourceDimensions, readerForPath, rePointSource } from "./readerInput";
import { bytes, displayTitle, inputCount, outputCount, specFor, retainedOutputs } from "./graph";
import type { Catalog, Graph, Parameter, RouteDefinition, TargetRef, ExecutionConfig, RemoteStatus, NodePatch } from "./types";

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
function CommaSeparatedInput({
  value,
  onChange,
  commitOnBlur = false,
  ...props
}: {
  value: unknown;
  onChange: (value: string[]) => void;
  id?: string;
  disabled: boolean;
  placeholder?: string;
  commitOnBlur?: boolean;
}) {
  const items = Array.isArray(value) ? value.map(String) : [];
  const serialized = JSON.stringify(items);
  const [text, setText] = useState(() => items.join(", "));
  const lastEmitted = useRef(serialized);
  useEffect(() => {
    // Preserve separators and spaces during our own edits; accept external edits/undo.
    if (serialized !== lastEmitted.current) {
      setText((JSON.parse(serialized) as string[]).join(", "));
      lastEmitted.current = serialized;
    }
  }, [serialized]);
  const commit = () => onChange(text.split(/[,，]/).map(item => item.trim()).filter(Boolean));
  return <input {...props} value={text} onBlur={() => {if (commitOnBlur) commit();}}
    onKeyDown={event => {if (commitOnBlur && event.key === 'Enter') event.currentTarget.blur();}} onChange={(event) => {
    const raw = event.target.value;
    const next = raw.split(/[,，]/).map(item => item.trim()).filter(Boolean);
    setText(raw);
    lastEmitted.current = JSON.stringify(next);
    if (!commitOnBlur) onChange(next);
  }} />;
}

export function ParameterField({
  field,
  value,
  onChange,
  disabled,
  onBrowse,
  onPath,
  baseDir = '.',
  target,
  onError,
}: {
  field: Parameter;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
  onBrowse?: import('./types').BrowseRemote;
  onPath?: (path: string, location: TargetRef) => void;
  baseDir?: string;
  target?: TargetRef;
  onError?: (message: string) => void;
}) {
  const id = `param-${field.key}`;
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  async function localFile(file?: File) {
    if (!file) return;
    setUploading(true);
    try {const result = await api.uploadReference(file, baseDir);
      if (onPath) onPath(result.path, {kind: 'local'}); else onChange(result.path);
    } catch (error) {onError?.((error as Error).message);}
    finally {setUploading(false); if (input.current) input.current.value = '';}
  }
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
      ) : field.type === "list" ? (
        <CommaSeparatedInput id={id} value={value} disabled={disabled}
          placeholder="用逗号分隔，如 PC1, PC2" onChange={onChange} />
      ) : (
        <input
          id={id}
          value={String(value ?? "")}
          disabled={disabled}
          onChange={(e) =>
            onChange(
              field.type === "scalar" && e.target.value.trim() !== "" && Number.isFinite(Number(e.target.value)) ? Number(e.target.value) : e.target.value,
            )
          }
        />
      )}
      {field.path_kind && <div className="path-actions">
        <input type="file" className="sr-only" ref={input} aria-label={`选择本机文件 ${field.label}`} onChange={e => void localFile(e.target.files?.[0])}/>
        <button type="button" className="subtle-button" disabled={disabled || uploading} onClick={() => input.current?.click()}>{uploading ? '导入中…' : '本机文件'}</button>
        {onBrowse && <button type="button" className="subtle-button" disabled={disabled || uploading} onClick={() => onBrowse(String(value || ''), (path, _source, location) => {
          if (onPath && location) onPath(path, location); else onChange(path);
        }, false, target)}>服务器文件</button>}
      </div>}
      {field.description && <HelpTip label={`${field.label}说明`}>{field.description}</HelpTip>}
    </label>
  );
}
export function ParameterGroups({parameters, renderField}: {parameters: Parameter[]; renderField: (field: Parameter) => import('react').ReactNode}) {
  return <div className="parameter-groups">{groupParameters(parameters).map(group => group.id === 'main'
    ? <div key={group.id} className="primary-parameters">{group.fields.map(renderField)}</div>
    : <details key={group.id} className="advanced parameter-section"><summary>{group.label}<CaretDown size={14}/></summary>{group.fields.map(renderField)}</details>)}</div>;
}
export function Inspector({
  graph,
  catalog,
  nodeId,
  settings,
  busy,
  uploadLimit,
  automaticMemoryFraction,
  automaticMemoryBudget,
  onNode,
  onMemory,
  onParams,
  onDelete,
  onError,
  onClose,
  onOpenRoute,
  onBrowseRemote,
  servers = [],
  onExecution = () => {},
  onFileLocation = () => {},
}: {
  graph: Graph;
  catalog: Catalog;
  nodeId: string | null;
  settings: boolean;
  busy: boolean;
  uploadLimit: number | null;
  automaticMemoryFraction?: number;
  automaticMemoryBudget?: number | null;
  onNode: (id: string, patch: NodePatch) => void;
  onMemory: (value: Graph["memory"]) => void;
  onParams: (value: Record<string, unknown>) => void;
  onDelete: (id: string) => void;
  onError: (message: string) => void;
  onClose: () => void;
  onOpenRoute: (route: RouteDefinition) => void;
  onBrowseRemote?: import('./types').BrowseRemote;
  servers?: RemoteStatus[];
  onExecution?: (patch: Partial<ExecutionConfig>) => void;
  onFileLocation?: (key: string, target: TargetRef) => void;
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
  const automaticPercent = automaticMemoryFraction == null ? undefined : automaticMemoryFraction * 100;
  const reader = node?.source ? readerForPath(catalog, node.source.path) : undefined;
  const retainedNames = node ? retainedOutputs(node, spec) : [];
  const sourceLocation = node?.source?.location ?? defaultTarget(graph);
  const pathTarget = (key: string) => executionConfig(graph).file_locations?.[key] ?? (node ? nodeTarget(graph, node.id) : defaultTarget(graph));
  function param(key: string, value: unknown) {
    if (!node) return;
    onNode(node.id, current => {
      const next = {...current.params};
      if (value === undefined) delete next[key]; else next[key] = value;
      return {params: next};
    });
  }
  async function upload(selection: FileList | null) {
    const files = Array.from(selection ?? []);
    if (!files.length || !node?.source) return;
    if (uploadLimit != null && files.some(file => file.size > uploadLimit * 1024 ** 2))
      return onError(`单个文件超过 ${uploadLimit} MiB，可改用项目内路径。`);
    setUploading(true);
    try {
      const result = await api.uploadFiles(files, graph.base_dir);
      onNode(node.id, {
        source: rePointSource(node.source, result.source, catalog),
        title: result.filename.replace(/\.(?:gz|bz2|xz)$/i, '').replace(/\.[^.]+$/, ''),
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
            <ExecutionSettings graph={graph} servers={servers} disabled={busy} onChange={onExecution}/>
            <div className="inspector-intro">
              <div className="node-icon">
                <HardDrives size={20} />
              </div>
              <h3>内存预算</h3>
              <HelpTip label="内存规划说明">显示启动时的预算估算，运行开始后更新为该次运行的实际预算。每次运行前扫描一次可用内存；运行期间由紧急溢写应对内存压力。</HelpTip>
            </div>
            <label className="toggle-field">
              <span><strong>内存管理</strong></span>
              <input type="checkbox" aria-label="内存管理" checked={memory.enabled} disabled={busy}
                onChange={e => onMemory({...memory, enabled: e.target.checked})}/><span className="toggle-track"/>
            </label>
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
              <div className="budget-summary">
                <dl><div><dt>分配比例</dt><dd>{automaticPercent == null ? "自动" : <>{automaticPercent}<small>%</small></>}</dd></div><div><dt>预算上限</dt><dd className="budget-value">{automaticMemoryBudget == null ? "无法读取" : bytes(automaticMemoryBudget)}</dd></div></dl>
                {automaticPercent != null && <div className="budget-proportion" aria-hidden="true"><span style={{width: `${automaticPercent}%`}}/></div>}
              </div>
            )}
            <label className="toggle-field">
              <span>
                <strong title="触及固定压力阈值时，释放未锁定数据">紧急溢写</strong>
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
              <JsonField label="完整内存配置 JSON" value={memory} disabled={busy}
                onChange={value => {
                  if (typeof value.enabled !== 'boolean') throw Error('enabled must be boolean');
                  onMemory(value as Graph['memory']);
                }}/>
            </details>
            <details className="advanced"><summary>全局参数 <CaretDown size={14}/></summary>
              <JsonField label="Pipeline params" value={graph.params || {}} disabled={busy} onChange={onParams}/>
            </details>
            <div className="section-rule" />
            <div className="capability" title="支线按依赖排序后依次运行。分块由算子的实际能力决定。">
              <Cpu size={17} />
              <span>资源充足时并行运行任务</span>
            </div>
          </>
        ) : node ? (
          <>
            <div className="inspector-intro">
              <div className="node-icon">
                <OperatorArtwork spec={spec} source={node.kind === "source"}/>
              </div>
              <h3>{displayTitle(node, spec)}</h3>
              {spec?.description && node.kind !== "source" && <HelpTip label="算子说明">{spec.description}</HelpTip>}
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
                  accept={inputAccept(catalog)}
                  multiple
                  className="sr-only"
                  aria-label="选择数据文件"
                  onChange={(e) => void upload(e.target.files)}
                />
                <button
                  className="upload-button"
                  disabled={busy || uploading}
                  onClick={() => fileInput.current?.click()}
                >
                  <FileArrowUp size={22} />
                  <strong>{uploading ? "正在导入…" : "选择本机文件"}</strong>
                  {uploadLimit != null && <small>每个文件上限 {uploadLimit} MiB</small>}
                </button>
                {onBrowseRemote && <button className="subtle-button source-server-button" disabled={busy || uploading}
                  onClick={() => onBrowseRemote(node.source!.path, (path, source, location) => onNode(node.id,
                    {source: {...(source || node.source!), path, location: location || sourceLocation}}), true, sourceLocation)}>选择服务器文件</button>}
                <details className="advanced input-format-help"><summary>多文件格式 <CaretDown size={14}/></summary>
                  <p className="helper">PLINK：同时选择同名的 .bed、.bim、.fam。10x MTX：同时选择 matrix、barcodes 和 features / genes。</p>
                </details>
                <label className="field"><span>文件所在位置</span><select aria-label="文件所在位置" value={targetKey(sourceLocation)} disabled={busy || uploading}
                  onChange={e => onNode(node.id, {source: {...node.source!, location: targetFromKey(e.target.value)}})}>
                  <option value="">本机</option>
                  {sourceLocation.kind === 'ssh' && !servers.some(server => server.profile.id === sourceLocation.profile_id) && <option value={sourceLocation.profile_id}>未配置的服务器</option>}
                  {servers.map(server => <option key={server.profile.id} value={server.profile.id}>{server.profile.name}</option>)}
                </select></label>
                <label className="field">
                  <span>{targetLabel(sourceLocation, servers)}文件路径</span>
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
                {reader?.contracts.output?.kind !== "file" && <label className="field">
                  <span>维度名称</span>
                  <CommaSeparatedInput
                    key={node.id}
                    commitOnBlur
                    value={node.source.dims}
                    disabled={busy}
                    onChange={(dims) => {
                      try { onNode(node.id, {source: renameSourceDimensions(node.source!, dims)}); }
                      catch (error) { onError((error as Error).message); }
                    }}
                  />
                </label>}
                {!!reader?.parameters?.length && <div className="reader-options">
                  <p className="section-caption">{reader.id} · 读取参数</p>
                  <ParameterGroups parameters={reader.parameters || []} renderField={field => <ParameterField key={`${node.id}-${field.key}`} field={field}
                    onBrowse={onBrowseRemote}
                    baseDir={graph.base_dir} target={pathTarget(`${node.id}.source.args.${field.key}`)} onError={onError}
                    onPath={(path, location) => {
                      onNode(node.id, current => ({source: {...current.source!, args: {...current.source!.args, [field.key]: path}}}));
                      onFileLocation(`${node.id}.source.args.${field.key}`, location);
                    }}
                    value={node.source!.args[field.key] ?? field.default} disabled={busy}
                    onChange={value => {
                      const args = {...node.source!.args};
                      if (value === undefined || value === '') delete args[field.key]; else args[field.key] = value;
                      onNode(node.id, {source: {...node.source!, args}});
                    }}/>}/>
                </div>}
                <details className="advanced">
                  <summary>
                    标签与完整读取选项 <CaretDown size={14} />
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
                </details>
              </>
            ) : (
              <>
                {node.kind === "route" && node.route && <div className="route-inspector">
                  <span className="route-version" title="当前画布保留这个版本的快照">路线算子 · v{node.route.version}</span>
                  <button className="subtle-button" onClick={() => onOpenRoute(node.route!)}><OperatorIcon name="Stack" size={17}/>打开路线的算子图</button>
                  <p className="helper">输入：{node.route.graph.interface?.inputs.map(p=>p.label).join(" / ") || "无"}</p>
                  <p className="helper">输出：{node.route.graph.interface?.outputs.map(p=>p.label).join(" / ") || "报告与图片"}</p>
                </div>}
                {node.kind !== "route" && <>
                <div className="section-caption">
                  参数 <span className="mono">{node.operator}</span>
                </div>
                <ParameterGroups parameters={spec?.parameters || []} renderField={(field) => (
                  <ParameterField
                    key={`${node.id}:${field.key}`}
                    field={field}
                    onBrowse={onBrowseRemote}
                    baseDir={graph.base_dir} target={pathTarget(`${node.id}.params.${field.key}`)} onError={onError}
                    onPath={(path, location) => {param(field.key, path); onFileLocation(`${node.id}.params.${field.key}`, location);}}
                    value={node.params[field.key] === undefined ? spec?.runtime_defaults?.[field.key] : node.params[field.key]}
                    disabled={busy}
                    onChange={(value) => param(field.key, value)}
                  />
                )}/>
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
                    {spec?.resources.supports_cuda ? "CPU / CUDA" : "CPU"}
                    {node.kind === "route" ? " · 共享外层内存规划" : spec?.resources.memory_modes.includes("stream")
                      ? " · 支持分块"
                      : " · 整体处理"}
                  </span>
                </div>
              </>
            )}
            {retainedNames.map((name, index) => (
              <label className="check-field" key={name} title="末端输出会自动保存，便于下载">
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
            <div className="inspector-empty-glyph" aria-hidden="true"><OperatorIcon size={24} weight="light"/><span/><span/></div>
            <h3>双击查看节点</h3>
          </div>
        )}
      </div>
    </aside>
  );
}
