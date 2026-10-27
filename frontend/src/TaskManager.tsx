import {CircleNotch, Clock, Stop} from '@phosphor-icons/react';
import {bytes} from './graph';
import {isActiveJob, jobPercent, jobStatusLabel} from './execution';
import type {Job} from './types';
import {ResourceSummary} from './ResourceSummary';

export function TaskProgress({job}: {job: Job}) {
  const percent = jobPercent(job), progress = job.progress;
  const transferring = progress?.bytes_total != null;
  return <div className="task-progress">
    <div className="task-progress-caption"><span>{progress?.current || jobStatusLabel[job.status]}</span>
      <small>{transferring ? `${bytes(progress.bytes_done || 0)} / ${bytes(progress.bytes_total!)}`
        : progress && progress.total > 0 ? `${progress.completed} / ${progress.total} 步` : ''}</small>
    </div>
    <progress aria-label={`${job.name}任务进度`} max="100" value={percent}/>
  </div>;
}
export function TaskManager({jobs, selectedId, onSelect, onCancel, onLogs, cancelling}: {
  jobs: Job[]; selectedId?: string; onSelect: (id: string) => void; onCancel?: (id: string) => void;
  onLogs: (id: string) => void; cancelling?: string;
}) {
  const active = jobs.filter(isActiveJob), finished = jobs.filter(job => !isActiveJob(job));
  return <div className="task-manager" aria-label="任务管理">
    <ResourceSummary/>
    {!jobs.length && <div className="results-empty"><Clock size={28}/><p>暂无任务</p></div>}
    {[{label: '正在执行', jobs: active}, {label: '最近完成', jobs: finished}].map(group => group.jobs.length > 0 && <section key={group.label}>
      <div className="task-section-title">{group.label}<span>{group.jobs.length}</span></div>
      {group.jobs.map(job => <div className={`task-row ${selectedId === job.id ? 'selected' : ''}`} key={job.id}>
        <button className="task-select" aria-label={`查看任务 ${job.name}`} aria-pressed={selectedId === job.id} onClick={() => onSelect(job.id)}>
          {isActiveJob(job) ? job.status === 'queued' ? <Clock size={18}/> : <CircleNotch size={18} className="spin"/> : <span className={`status-dot ${job.status}`}/>}
          <span><strong>{job.name}</strong><small>{job.remote?.name || 'BioPipe'} · {job.id.slice(-8)}</small></span>
        </button>
        <TaskProgress job={job}/>
        <span className={`status-label ${job.status}`}>{jobStatusLabel[job.status]}</span>
        <div className="task-actions"><button className="text-button" onClick={() => onLogs(job.id)}>日志</button>
          {isActiveJob(job) && onCancel && <button className="icon-button" aria-label={`停止任务 ${job.name}`} disabled={cancelling === job.id}
            onClick={() => onCancel(job.id)}>{cancelling === job.id ? <CircleNotch size={15} className="spin"/> : <Stop size={15}/>}</button>}
        </div>
      </div>)}
    </section>)}
  </div>;
}
