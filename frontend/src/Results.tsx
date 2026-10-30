import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowSquareOut,
  CaretDown,
  CheckCircle,
  ChartScatter,
  CircleNotch,
  Clock,
  FileCode,
  Play,
  Terminal,
  WarningCircle,
} from "@phosphor-icons/react";
import { api } from "./api";
import { bytes } from "./graph";
import {isActiveJob, jobStatusLabel} from './execution';
import {TaskManager, TaskProgress} from './TaskManager';
import {FigureLinks, figureFormats, figureGroups, FigureGallery} from './FigureOutputs';
import type { Job, Preview, RunEvent, SpillCounts } from "./types";

export const statusLabel = jobStatusLabel;
const eventNames: Record<string, string> = {
  worker_launching: "启动进程",
  worker_spawned: "进程已启动",
  worker_started: "初始化引擎",
  worker_start_failed: "启动失败",
  worker_finished: "进程退出",
  worker_interrupted: "进程中断",
  step_started: "步骤开始",
  operator_log: "算子日志",
  run_started: "运行开始",
  plan_compiled: "固定顺序已编译",
  step_plan: "步骤规划",
  step_finished: "步骤完成",
  run_finished: "运行结束",
  spill: "数据落盘",
  load: "数据回读",
  source_loaded: "读取输入",
  source_prepare_started: "开始分块稠密化",
  densify_block_spill: "稠密化缓冲块落盘",
  source_prepare_complete: "稠密化完成，交接规划器",
  source_blocks_released: "释放稠密化缓存块",
  emergency_spill: "紧急溢写检查",
  registered: "注册产物",
  register: "注册产物",
  released: "释放数据",
  release: "释放数据",
  spill_blocked: "溢写受阻",
};
const reasons: Record<string, string> = {
  full_step_admission: "规划落盘",
  final_output: "最终产物保存",
  rss_pressure: "RSS 压力",
  managed_pressure: "数据预算压力",
  actual_output_size: "真实输出大小校正",
  actual_input_size: "真实输入大小校正",
  step_boundary: "步骤边界校正",
  stream_admission: "分块预留",
  cache_admission: "缓存准入",
  buffer_watermark: "稠密化缓冲水位",
  phase_handoff: "阶段交接",
  full_mode_admission: "整体计算预留",
};
export function spillCounts(events: RunEvent[]): SpillCounts {
  const result: SpillCounts = {
    planned: 0,
    emergency: 0,
    correction: 0,
    final: 0,
  };
  for (const event of events)
    if (event.event === "spill") {
      const reason = event.reason;
      const kind =
        reason === "final_output"
          ? "final"
          : ["rss_pressure", "managed_pressure"].includes(reason || "")
            ? "emergency"
            : [
                  "actual_output_size",
                  "actual_input_size",
                  "step_boundary",
                ].includes(reason || "")
              ? "correction"
              : "planned";
      result[kind]++;
    }
  return result;
}
function Scatter({ preview }: { preview: Preview }) {
  const points = preview.points.filter(
    (p): p is [number, number] =>
      p.length >= 2 &&
      p[0] !== null &&
      p[1] !== null &&
      Number.isFinite(p[0]) &&
      Number.isFinite(p[1]),
  );
  if (!points.length)
    return <div className="mini-empty">没有可绘制的有限数值</div>;
  const xs = points.map((p) => p[0]),
    ys = points.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxX = Math.max(...xs),
    minY = Math.min(...ys),
    maxY = Math.max(...ys);
  const x = (v: number) => 34 + ((v - minX) / (maxX - minX || 1)) * 276;
  const y = (v: number) => 133 - ((v - minY) / (maxY - minY || 1)) * 108;
  return (
    <svg
      className="scatter"
      viewBox="0 0 340 161"
      role="img"
      aria-label={`前两列散点图，共 ${points.length} 个预览点`}
    >
      {[25, 61, 97, 133].map((v) => (
        <line key={v} x1="34" x2="310" y1={v} y2={v} stroke="var(--border)" />
      ))}
      <line x1="34" x2="310" y1="133" y2="133" stroke="var(--border-strong)" />
      <line x1="34" x2="34" y1="25" y2="133" stroke="var(--border-strong)" />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={x(p[0])}
          cy={y(p[1])}
          r="2.5"
          fill="var(--accent)"
          opacity=".8"
        >
          <title>
            {p[0].toFixed(3)}, {p[1].toFixed(3)}
          </title>
        </circle>
      ))}
      <text x="172" y="155" textAnchor="middle">
        第 1 列
      </text>
      <text x="13" y="79" textAnchor="middle" transform="rotate(-90 13 79)">
        第 2 列
      </text>
      <text x="34" y="146" textAnchor="middle" className="tick">
        {minX.toFixed(1)}
      </text>
      <text x="310" y="146" textAnchor="middle" className="tick">
        {maxX.toFixed(1)}
      </text>
    </svg>
  );
}
export function Results({
  job,
  events,
  consoleText = "",
  consoleTruncated = false,
  history,
  tab,
  onTab,
  onJob,
  onRestore,
  onError,
  collapsed,
  onToggle,
  stale,
  onCancel,
  cancelling,
}: {
  job: Job | null;
  events: RunEvent[];
  consoleText?: string;
  consoleTruncated?: boolean;
  history: Job[];
  tab: string;
  onTab: (tab: string) => void;
  onJob: (id: string) => void | Promise<void>;
  onRestore: (job: Job) => void;
  onError: (message: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  stale: boolean;
  onCancel?: (id: string) => void;
  cancelling?: string;
}) {
  const [preview, setPreview] = useState<Preview | null>(null),
    [selected, setSelected] = useState(""),
    [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState(''), [previewError, setPreviewError] = useState('');
  const [reload, setReload] = useState(0);
  const selectionRequest = useRef(0);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null),
    [step, setStep] = useState(-1);
  const reportRequest = useRef(0);
  const [focusedFigure, setFocusedFigure] = useState<string | undefined>(undefined);
  const artifacts = job?.report?.artifacts.filter((a) => a.disk_uri) || [];
  const hasOutputs = artifacts.length > 0 || !!job?.summary?.steps.length;
  const savedFormats = figureFormats(detail);
  const savedFigures = job?.summary?.steps.flatMap((item, index) => {
    return figureGroups(item).map(group => ({...item, index, ...group}));
  }) || [];
  async function openJob(id: string, destination: string) {
    const request = ++selectionRequest.current;
    setOpening(id);
    try {
      await onJob(id);
      if (request === selectionRequest.current) onTab(destination);
    } catch (error) {
      if (request === selectionRequest.current) onError((error as Error).message);
    } finally {
      if (request === selectionRequest.current) setOpening('');
    }
  }
  useEffect(() => {
    reportRequest.current++;
    setPreview(null);
    setSelected("");
    setDetail(null);
    setStep(-1);
    setPreviewError('');
    setLoading(false);
  }, [job?.id]);
  useEffect(() => {
    if (!job || tab !== 'results' || step >= 0 || !artifacts.length) return;
    const id =
      selected && artifacts.some((a) => a.artifact_id === selected)
        ? selected
        : artifacts[artifacts.length - 1].artifact_id;
    let alive = true;
    setLoading(true);
    setPreviewError('');
    api
      .preview(job.id, id)
      .then((value) => {
        if (alive) {
          setPreview(value);
          setSelected(id);
        }
      })
      .catch((error) => {
        if (alive) setPreviewError(error.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [
    job?.id,
    job?.status,
    tab,
    step,
    reload,
    selected,
    artifacts.map((a) => a.artifact_id).join(","),
  ]);
  async function report(index: number, figureId?: string) {
    if (!job) return;
    const request = ++reportRequest.current;
    setStep(index);
    setFocusedFigure(figureId);
    setDetail(null);
    setPreviewError('');
    const jobId = job.id;
    try {
      const value = await api.step(jobId, index);
      if (request === reportRequest.current) setDetail(value);
    } catch (error) {
      if (request === reportRequest.current) setPreviewError((error as Error).message);
    }
  }
  useEffect(() => {
    if (tab === 'results' && !artifacts.length && job?.summary?.steps.length && step < 0) void report(0);
  }, [tab, job?.id, artifacts.length, job?.summary?.steps.length, step]);
  const counts = job?.spill_counts || spillCounts(events);
  const completed = events.filter((e) => e.event === "step_finished").length;
  return (
    <section className="results-panel" aria-label="运行结果与日志">
      <div className="results-heading">
        <div className="result-tabs" role="tablist" aria-label="结果面板">
          {[
            ["results", "结果"],
            ["logs", "运行日志"],
            ['tasks', '任务'],
            ["history", "运行记录"],
          ].map(([key, label]) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              className={tab === key ? "active" : ""}
              onClick={() => onTab(key)}
            >
              {label}
              {key === "history" && history.length > 0 && (
                <span>{history.length}</span>
              )}
              {key === 'tasks' && history.some(isActiveJob) && <span>{history.filter(isActiveJob).length}</span>}
            </button>
          ))}
        </div>
        <div className="run-caption">
          {job ? (
            <>
              <span className={`status-dot ${job.status}`} />
              <span>
                {stale ? "上次运行 · 画布已修改" : statusLabel[job.status]}
                {job.status === "running"
                  ? ` · ${completed}/${job.order?.length || 0} 步`
                  : ""}
              </span>
              <span className="mono run-id">{job.id.slice(-8)}</span>
            </>
          ) : (
            <span>未运行</span>
          )}
          <button
            className={`icon-button result-toggle ${collapsed ? "closed" : ""}`}
            aria-label={collapsed ? "展开结果面板" : "收起结果面板"}
            title={collapsed ? "展开结果面板" : "收起结果面板"}
            onClick={onToggle}
          >
            <CaretDown size={14} />
          </button>
        </div>
      </div>
      <div className="results-body">
        {tab === 'tasks' ? <TaskManager jobs={history} selectedId={job?.id} onSelect={id => void openJob(id, 'results')} onCancel={onCancel} cancelling={cancelling}
          onLogs={id => void openJob(id, 'logs')}/> : tab === "history" ? (
          <div className="history-list">
            {history.length ? (
              history.map((item) => (
                <div className={`history-item ${job?.id === item.id ? 'selected' : ''}`} key={item.id} aria-busy={opening === item.id}>
                  {opening === item.id ? <CircleNotch size={17} className="spin"/> : <Clock size={17} />}
                  <button
                    className="history-name"
                    onClick={() => void openJob(item.id, 'results')}
                    aria-label={`查看结果 ${item.name}`}
                  >
                    <strong>{item.name}</strong>
                    <small>
                      {new Date(item.created_at).toLocaleString("zh-CN", {
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}{" "}
                      · {item.id.slice(-8)}
                    </small>
                  </button>
                  <span className={`status-label ${item.status}`}>
                    {statusLabel[item.status]}
                  </span>
                  <div className="history-actions">
                  <button className="text-button history-view" onClick={() => void openJob(item.id, 'results')}>
                    <ChartScatter size={15}/>{isActiveJob(item) ? '查看进度' : '查看结果'}
                  </button>
                  <button className="text-button" onClick={() => void openJob(item.id, 'logs')}>
                    <Terminal size={15}/>查看日志
                  </button>
                  <button
                    className="text-button"
                    onClick={() => {
                      void api
                        .job(item.id)
                        .then(onRestore)
                        .catch((e) => onError(e.message));
                    }}
                  >
                    载入画布
                  </button>
                  </div>
                </div>
              ))
            ) : (
              <div className="results-empty">
                <Clock size={29} weight="light" />
                <p>暂无运行记录</p>
              </div>
            )}
          </div>
        ) : tab === "logs" ? (
          <div className="log-layout">
            <div className="event-list">
              {job?.error && <div className="log-error" role="alert"><WarningCircle size={18} /><span>{job.error}</span></div>}
              {events.length ? (
                events.slice(-200).map((event, index) => (
                  <div
                    className={`event-line ${event.error || event.event === "spill_blocked" ? "warn" : ""}`}
                    key={`${event.time}-${index}`}
                  >
                    <time>
                      {new Date(event.time).toLocaleTimeString("zh-CN", {
                        hour12: false,
                      })}
                    </time>
                    <strong>{eventNames[event.event] || event.event}</strong>
                    <span>
                      {event.name || ""}
                      {event.message ? `${event.name ? " · " : ""}${event.message}` : ""}
                      {event.reason
                        ? ` · ${reasons[event.reason] || event.reason}`
                        : ""}
                      {event.event === "step_plan"
                        ? ` · ${event.mode === "stream" ? "分块执行" : "整体执行"}`
                        : ""}
                      {event.error ? ` · ${event.error}` : ""}
                    </span>
                  </div>
                ))
              ) : !job?.error && !consoleText ? (
                <div className="results-empty">
                  <Terminal size={29} weight="light" />
                  <p>暂无运行日志</p>
                </div>
              ) : null}
              {consoleText && (
                <details className="process-console" key={job?.id} open={job?.status === "failed" || !events.length}>
                  <summary><Terminal size={16} />进程输出{consoleTruncated ? " · 最近输出" : ""}</summary>
                  <pre>{consoleText}</pre>
                </details>
              )}
            </div>
            <div className="resource-metrics">
              <h3>存储事件</h3>
              {(
                [
                  ["planned", "规划落盘"],
                  ["emergency", "紧急溢写"],
                  ["correction", "大小校正"],
                  ["final", "产物保存"],
                ] as const
              ).map(([key, label]) => (
                <div key={key}>
                  <span>{label}</span>
                  <strong>{counts[key]}</strong>
                </div>
              ))}
              {job && (
                <a
                  href={api.url(`/api/jobs/${job.id}/console`)}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ArrowSquareOut size={14} />
                  完整进程日志
                </a>
              )}
            </div>
          </div>
        ) : !job ? (
          <div className="results-empty">
            <div className="empty-icon">
              <Play size={23} weight="light" />
            </div>
            <div>
              <h3>暂无运行结果</h3>
            </div>
          </div>
        ) : job.error && !hasOutputs ? (
          <div className="run-error">
            <WarningCircle size={24} />
            <div>
              <h3>{statusLabel[job.status]}</h3>
              <p>{job.error}</p>
              <button className="text-button" onClick={() => onTab("logs")}>
                查看运行日志
              </button>
            </div>
          </div>
        ) : isActiveJob(job) ? (
          <div className="results-empty">
            <div className="empty-icon pulse">
              <ChartScatter size={24} />
            </div>
            <div>
              <h3>{statusLabel[job.status]}</h3>
              <TaskProgress job={job}/>
              <button className="text-button" onClick={() => onTab('tasks')}>查看所有任务</button>
            </div>
          </div>
        ) : (
          <div className="result-content">
            <div className="artifact-sidebar">
              {job.remote && <div className="result-location" title={`${job.remote.workspace}/.studio/jobs/${job.remote.job_id}`}>{job.remote.name}</div>}
              {savedFigures.length > 0 && <>
                <div className="section-caption">输出图表 <span>{savedFigures.length}</span></div>
                {savedFigures.map(item => <div className="saved-figure" key={`${item.index}:${item.id}`}>
                  <button className="text-button" onClick={() => void report(item.index, item.id)}><ChartScatter size={15}/>{item.title}</button>
                  <FigureLinks jobId={job.id} step={item.index} formats={item.formats} figureId={item.id === "__legacy__" ? undefined : item.id} compact/>
                </div>)}
              </>}
              <div className="section-caption">
                数据产物 <span>{artifacts.length}</span>
              </div>
              {artifacts.map((artifact) => (
                <button
                  key={artifact.artifact_id}
                  className={`artifact-option ${selected === artifact.artifact_id && step < 0 ? "active" : ""}`}
                  onClick={() => {
                    reportRequest.current++;
                    setPreviewError('');
                    setSelected(artifact.artifact_id);
                    setStep(-1);
                  }}
                >
                  <FileCode size={16} />
                  <span>
                    <strong>{artifact.name}</strong>
                    <small>
                      {artifact.shape.join(" × ")} ·{" "}
                      {bytes(artifact.ram_estimate_bytes)}
                    </small>
                  </span>
                </button>
              ))}
              <div className="section-caption">步骤报告</div>
              {job.summary?.steps.map((item, index) => (
                <button
                  className={`step-option ${step === index ? "active" : ""}`}
                  key={index}
                  onClick={() => void report(index)}
                >
                  <CheckCircle size={14} />
                  <span>
                    {String(index + 1).padStart(2, "0")} · {item.name}
                  </span>
                </button>
              ))}
            </div>
            <div className="preview-content">
              {job.error && <div className="result-warning" role="alert"><WarningCircle size={16}/><span>{job.error}</span><button className="text-button" onClick={() => onTab('logs')}>查看日志</button></div>}
              {previewError ? <div className="result-warning" role="alert"><WarningCircle size={18}/><span>{previewError}</span><button className="text-button" onClick={() => step >= 0 ? void report(step) : setReload(value => value + 1)}>重试</button></div> : step >= 0 ? (
                <>
                  <div className="preview-heading">
                    <strong>步骤 {step + 1} · 分析报告</strong>
                    <a
                      className="text-button"
                      href={api.url(
                        `/api/jobs/${job.id}/exports/${step}/download`,
                      )}
                    >
                      <ArrowDown size={14} />
                      JSON
                    </a>
                  </div>
                  {savedFormats.length ? (
                    <FigureGallery jobId={job.id} step={step} report={detail!} focusId={focusedFigure}/>
                  ) : (
                    <pre className="report-json">
                      {detail
                        ? JSON.stringify(detail, null, 2)
                        : "正在读取报告…"}
                    </pre>
                  )}
                </>
              ) : preview && !loading ? (
                <>
                  <div className="preview-heading">
                    <strong>
                      {preview.descriptor.name}
                      <span>
                        {preview.format || `${preview.descriptor.shape.join(" × ")} · ${preview.descriptor.dtype}`}
                      </span>
                    </strong>
                    <a
                      className="text-button"
                      href={api.url(
                        `/api/jobs/${job.id}/artifacts/${selected}/download`,
                      )}
                    >
                      <ArrowDown size={14} />
                      {preview.format ? "下载文件清单" : "下载 .npy"}
                    </a>
                  </div>
                  <div className="data-preview">
                    {preview.files?.map(file => (
                      file.downloadable ? <a key={file.role} className="text-button" href={api.url(`/api/jobs/${job.id}/artifacts/${selected}/files/${encodeURIComponent(file.role)}`)}>
                        <ArrowDown size={14} /> {file.name} · {(file.bytes / 1024 ** 2).toFixed(2)} MiB
                      </a> : <span key={file.role}>{file.name} · {(file.bytes / 1024 ** 2).toFixed(2)} MiB</span>
                    ))}
                    {preview.points.length > 0 && (
                      <div className="chart-preview">
                        <Scatter preview={preview} />
                        <small>数据预览 · 前两列 · 最多 200 行</small>
                      </div>
                    )}
                    {!preview.format && <div className="table-preview">
                      <table>
                        <caption className="sr-only">
                          产物预览，最多 20 行与 8 列
                        </caption>
                        <thead>
                          <tr>
                            <th>#</th>
                            {preview.rows[0]?.map((_, i) => (
                              <th key={i}>列 {i + 1}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {preview.rows.map((row, i) => (
                            <tr key={i}>
                              <th>{i + 1}</th>
                              {row.map((value, j) => (
                                <td key={j}>
                                  {value === null
                                    ? "—"
                                    : Number(value).toFixed(3)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>}
                  </div>
                </>
              ) : (
                <div className="mini-empty">
                  {loading
                    ? "正在读取产物…"
                    : "本次运行没有保存可查看的产物。"}
                </div>
              )}
            </div>
            <div className="resource-metrics">
              <h3>内存记录</h3>
              <div>
                <span>固定数据预算</span>
                <strong>{bytes(job.report?.budget_bytes)}</strong>
              </div>
              <div>
                <span>数据峰值</span>
                <strong>{bytes(job.report?.managed_peak_bytes)}</strong>
              </div>
              <div>
                <span>进程 RSS 峰值</span>
                <strong>{bytes(job.report?.sampled_rss_peak_bytes)}</strong>
              </div>
              <div>
                <span>紧急溢写</span>
                <strong>{counts.emergency}</strong>
              </div>
              <small>RSS 包含运行环境；数据峰值不含全部进程开销。</small>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
