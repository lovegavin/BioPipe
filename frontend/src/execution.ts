import type {ExecutionConfig, Graph, Job, Parameter, RemoteStatus, RunEvent, TargetRef} from './types';

export const jobStatusLabel: Record<Job['status'], string> = {
  queued: '等待资源', preparing: '准备中', uploading: '上传中', waiting_connection: '等待连接', running: '运行中',
  complete: '已完成', failed: '失败', cancelled: '已停止', interrupted: '已中断',
};
export function isActiveJob(job: Pick<Job, 'status'> | null | undefined): boolean {
  return !!job && ['queued', 'preparing', 'uploading', 'waiting_connection', 'running'].includes(job.status);
}
export function executionConfig(graph: Graph): ExecutionConfig {
  const value = graph.runtime?.execution as ExecutionConfig | undefined;
  return {kind: 'local', ...value, mode: value?.mode ?? 'manual'};
}
export function withExecution(graph: Graph, patch: Partial<ExecutionConfig>): Graph {
  return {...graph, runtime: {...graph.runtime, execution: {...executionConfig(graph), ...patch}}};
}
export function defaultTarget(graph: Graph): TargetRef {
  const config = executionConfig(graph);
  return config.kind === 'ssh' ? {kind: 'ssh', profile_id: config.profile_id || ''} : {kind: 'local'};
}
export function nodeTarget(graph: Graph, id: string): TargetRef {
  return executionConfig(graph).node_targets?.[id] ?? defaultTarget(graph);
}
export function targetKey(target: TargetRef): string { return target.kind === 'ssh' ? target.profile_id : ''; }
export function targetFromKey(key: string): TargetRef {return key ? {kind: 'ssh', profile_id: key} : {kind: 'local'};}
export function targetLabel(target: TargetRef, servers: RemoteStatus[]): string {
  return target.kind === 'local' ? '本机' : servers.find(s => s.profile.id === target.profile_id)?.profile.name || '未配置的服务器';
}
export function assignNodeTarget(graph: Graph, id: string, target?: TargetRef): Graph {
  if (executionConfig(graph).mode === 'auto') return graph;
  // Only top-level IDs are eligible. A route is one atomic placement unit.
  if (!graph.nodes.some(node => node.id === id && node.kind !== 'source')) return graph;
  const targets = {...executionConfig(graph).node_targets};
  if (target) targets[id] = target; else delete targets[id];
  return withExecution(graph, {node_targets: targets});
}
export function withFileLocation(graph: Graph, key: string, target: TargetRef): Graph {
  return withExecution(graph, {file_locations: {...executionConfig(graph).file_locations, [key]: target}});
}
export function withoutNodeExecution(graph: Graph, ids: string[]): Graph {
  const config = executionConfig(graph);
  return withExecution(graph, {
    node_targets: Object.fromEntries(Object.entries(config.node_targets || {}).filter(([id]) => !ids.includes(id))),
    file_locations: Object.fromEntries(Object.entries(config.file_locations || {}).filter(([key]) => !ids.some(id => key.startsWith(`${id}.params.`) || key.startsWith(`${id}.source.args.`)))),
  });
}
export function jobPercent(job: Job): number | undefined {
  if (job.status === 'complete') return 100;
  const progress = job.progress;
  if (!progress) return undefined;
  const computed = progress.percent ?? (progress.bytes_total ? 100 * (progress.bytes_done || 0) / progress.bytes_total
    : progress.total ? 100 * progress.completed / progress.total : undefined);
  return computed !== undefined && Number.isFinite(computed) ? Math.min(100, Math.max(0, computed)) : undefined;
}
export function nodeStatuses(events: RunEvent[], job: Job | null, stale = false): Record<string, string> {
  const result: Record<string, string> = {};
  if (stale) return result;
  let current = -1;
  for (const event of events) {
    if (event.event === 'step_started' || event.event === 'step_plan') {
      current = Number(event.index) - 1;
      const id = typeof event.node_id === 'string' ? event.node_id : job?.order?.[current];
      if (id) result[id] = 'running';
    }
    if (event.event === 'step_finished') {
      const index = typeof event.index === 'number' ? event.index - 1 : current;
      const id = typeof event.node_id === 'string' ? event.node_id : job?.order?.[index];
      if (id) result[id] = event.node_finished === false ? 'running' : 'finished';
    }
  }
  if (job?.status === 'complete') {
    const ids = job.order || job.execution_plan?.units.flatMap(unit => unit.node_ids) || [];
    for (const id of ids) result[id] = 'finished';
  }
  for (const owner of new Set(Object.values(job?.node_owners || {}))) {
    const steps = (job?.order || []).filter(id => job?.node_owners?.[id] === owner);
    if (steps.length && steps.every(id => result[id] === 'finished')) result[owner] = 'finished';
    else if (steps.some(id => result[id])) result[owner] = 'running';
  }
  return result;
}
export type ParameterGroup = {id: 'main' | 'environment' | 'resources' | 'advanced'; label: string; fields: Parameter[]};
export function groupParameters(parameters: Parameter[]): ParameterGroup[] {
  const groups: ParameterGroup[] = [
    {id: 'main', label: '分析参数', fields: []}, {id: 'environment', label: '工具与环境', fields: []},
    {id: 'resources', label: '资源与性能', fields: []}, {id: 'advanced', label: '高级参数', fields: []},
  ];
  const environment = /^(executor|backend|wsl(_.*)?|tool(_.*)?|.*_executable|executable|container|conda(_.*)?)$/;
  const resources = /^(threads?|n_threads|n_jobs|workers?|cpus?|memory(_.*)?|.*_memory(_.*)?|timeout(_.*)?|chunk(_.*)?|batch_size)$/;
  for (const field of parameters) {
    const key = field.key.toLowerCase();
    const id = field.group ?? (environment.test(key) ? 'environment' : resources.test(key) ? 'resources' : key.startsWith('figure_') ? 'advanced' : 'main');
    (groups.find(group => group.id === id) ?? groups[0]).fields.push(field);
  }
  const priority = (field: Parameter) => field.priority ?? (/^(methods?|analysis|mode)$/.test(field.key) ? -20 : field.required ? -10 : 0);
  for (const group of groups) group.fields.sort((a, b) => priority(a) - priority(b));
  return groups.filter(group => group.fields.length);
}
