import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowSquareOut,
  CaretDown,
  CheckCircle,
  ChartScatter,
  Clock,
  FileCode,
  Play,
  Terminal,
  WarningCircle,
} from "@phosphor-icons/react";
import { api } from "./api";
import { bytes } from "./graph";
import type { Job, Preview, RunEvent, SpillCounts } from "./types";

export const statusLabel: Record<Job["status"], string> = {
  running: "运行中",
  complete: "已完成",
  failed: "失败",
  cancelled: "已停止",
  interrupted: "已中断",
};
const eventNames: Record<string, string> = {
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
  history,
  tab,
  onTab,
  onJob,
  onRestore,
  onError,
  collapsed,
  onToggle,
  stale,
}: {
  job: Job | null;
  events: RunEvent[];
  history: Job[];
  tab: string;
  onTab: (tab: string) => void;
  onJob: (id: string) => void;
  onRestore: (job: Job) => void;
  onError: (message: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  stale: boolean;
}) {
  const [preview, setPreview] = useState<Preview | null>(null),
    [selected, setSelected] = useState(""),
    [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null),
    [step, setStep] = useState(-1);
  const reportRequest = useRef(0);
  const artifacts = job?.report?.artifacts.filter((a) => a.disk_uri) || [];
  useEffect(() => {
    reportRequest.current++;
    setPreview(null);
    setSelected("");
    setDetail(null);
    setStep(-1);
  }, [job?.id]);
  useEffect(() => {
    if (!job || !artifacts.length) return;
    const id =
      selected && artifacts.some((a) => a.artifact_id === selected)
        ? selected
        : artifacts[artifacts.length - 1].artifact_id;
    let alive = true;
    setLoading(true);
    api
      .preview(job.id, id)
      .then((value) => {
        if (alive) {
          setPreview(value);
          setSelected(id);
        }
      })
      .catch((error) => {
        if (alive) onError(error.message);
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
    selected,
    artifacts.map((a) => a.artifact_id).join(","),
  ]);
  async function report(index: number) {
    if (!job) return;
    const request = ++reportRequest.current;
    setStep(index);
    setDetail(null);
    const jobId = job.id;
    try {
      const value = await api.step(jobId, index);
      if (request === reportRequest.current) setDetail(value);
    } catch (error) {
      onError((error as Error).message);
    }
  }
  const counts = job?.spill_counts || spillCounts(events);
  const completed = events.filter((e) => e.event === "step_finished").length;
  return (
    <section className="results-panel" aria-label="运行结果与日志">
      <div className="results-heading">
        <div className="result-tabs" role="tablist" aria-label="结果面板">
          {[
            ["results", "结果"],
            ["logs", "运行日志"],
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
        {tab === "history" ? (
          <div className="history-list">
            {history.length ? (
              history.map((item) => (
                <div className="history-item" key={item.id}>
                  <Clock size={17} />
                  <button
                    className="history-name"
                    disabled={job?.status === "running"}
                    onClick={() => onJob(item.id)}
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
                  <button
                    className="text-button"
                    onClick={() => {
                      void api
                        .job(item.id)
                        .then(onRestore)
                        .catch((e) => onError(e.message));
                    }}
                    disabled={job?.status === "running"}
                  >
                    载入画布
                  </button>
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
              {events.length ? (
                events.slice(-200).map((event, index) => (
                  <div
                    className={`event-line ${event.event === "spill_blocked" ? "warn" : ""}`}
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
              ) : (
                <div className="results-empty">
                  <Terminal size={29} weight="light" />
                  <p>暂无运行日志</p>
                </div>
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
        ) : job.error ? (
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
        ) : job.status === "running" ? (
          <div className="results-empty">
            <div className="empty-icon pulse">
              <ChartScatter size={24} />
            </div>
            <div>
              <h3>正在执行工作流</h3>
            </div>
          </div>
        ) : (
          <div className="result-content">
            <div className="artifact-sidebar">
              <div className="section-caption">
                数据产物 <span>{artifacts.length}</span>
              </div>
              {artifacts.map((artifact) => (
                <button
                  key={artifact.artifact_id}
                  className={`artifact-option ${selected === artifact.artifact_id && step < 0 ? "active" : ""}`}
                  onClick={() => {
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
              {step >= 0 ? (
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
                  {detail?.path &&
                  /\.(png|jpg|jpeg|webp|svg)$/i.test(
                    String(detail.filename || ""),
                  ) ? (
                    <div className="figure-preview">
                      <img
                        src={api.url(
                          `/api/jobs/${job.id}/exports/${step}/figure`,
                        )}
                        alt={`${detail.kind || "分析"}图像产物`}
                      />
                      <a
                        href={api.url(
                          `/api/jobs/${job.id}/exports/${step}/figure`,
                        )}
                        target="_blank"
                        rel="noreferrer"
                        className="text-button"
                      >
                        <ArrowSquareOut size={13} />
                        查看原图
                      </a>
                    </div>
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
                        {preview.descriptor.shape.join(" × ")} ·{" "}
                        {preview.descriptor.dtype}
                      </span>
                    </strong>
                    <a
                      className="text-button"
                      href={api.url(
                        `/api/jobs/${job.id}/artifacts/${selected}/download`,
                      )}
                    >
                      <ArrowDown size={14} />
                      下载 .npy
                    </a>
                  </div>
                  <div className="data-preview">
                    {preview.points.length > 0 && (
                      <div className="chart-preview">
                        <Scatter preview={preview} />
                        <small>前两列 · 最多 200 行</small>
                      </div>
                    )}
                    <div className="table-preview">
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
                    </div>
                  </div>
                </>
              ) : (
                <div className="mini-empty">
                  {loading
                    ? "正在读取产物…"
                    : "本次运行没有保留数组产物，可查看步骤报告。"}
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
