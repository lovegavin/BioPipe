import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {EnvironmentMenu, ExecutionSettings} from './ExecutionSettings';
import {ParameterGroups, ParameterField, Inspector} from './Inspector';
import {TaskManager, TaskProgress} from './TaskManager';
import {assignNodeTarget, defaultTarget, executionConfig, groupParameters, isActiveJob, jobPercent, nodeStatuses, nodeTarget, withExecution, withFileLocation, withoutNodeExecution} from './execution';
import {normalizeGraph} from './graph';
import {copyFragment, pasteFragment} from './editing';
import type {Graph, Job, Parameter, RemoteStatus, Catalog} from './types';

const graph: Graph = {schema_version: 2, name: 'Hi-C', base_dir: '.', memory: {enabled: true, budget_mb: 400}, edges: [], nodes: [
  {id: 'structure', kind: 'operator', operator: 'structure', title: 'Hi-C structure', position: {x: 0, y: 0}, input_count: 1,
    params: {method: 'insulation', threads: 3, memory_mb: 256, view: 'regions.bed'}},
]};
const fields: Parameter[] = [
  {key: 'executor', label: 'Executor', type: 'choice', options: ['native', 'wsl']},
  {key: 'threads', label: 'Threads', type: 'integer'},
  {key: 'memory_mb', label: 'Memory', type: 'integer'},
  {key: 'timeout_seconds', label: 'Timeout', type: 'integer'},
  {key: 'tool_paths', label: 'Tools', type: 'json'},
  {key: 'window', label: 'Window', type: 'integer'},
  {key: 'view', label: 'View', type: 'string', required: true, path_kind: 'source'},
  {key: 'method', label: 'Method', type: 'choice', options: ['expected', 'insulation', 'loops']},
];
const servers = [{profile: {id: 'ssh-a', name: 'Compute'}, connected: true}] as RemoteStatus[];
const job: Job = {id: 'job-a', name: 'Genome A', created_at: '2026-10-27T00:00:00Z', status: 'uploading',
  progress: {phase: 'uploading', completed: 0, total: 4, bytes_done: 256, bytes_total: 1024, current: 'reads.fastq.gz'}};

describe('parameter hierarchy', () => {
  it('promotes method and required fields, then folds generic environment/resources without losing parameters', () => {
    const groups = groupParameters(fields);
    expect(groups[0].fields.map(field => field.key)).toEqual(['method', 'view', 'window']);
    expect(groups.find(group => group.id === 'environment')?.fields.map(field => field.key)).toEqual(['executor', 'tool_paths']);
    expect(groups.find(group => group.id === 'resources')?.fields.map(field => field.key)).toEqual(['threads', 'memory_mb', 'timeout_seconds']);
    expect(groups.flatMap(group => group.fields)).toHaveLength(fields.length);
    const html = renderToStaticMarkup(<ParameterGroups parameters={fields} renderField={field => <ParameterField key={field.key} field={field}
      value={graph.nodes[0].params[field.key]} disabled={false} onChange={() => {}}/>}/>);
    expect(html.indexOf('param-method')).toBeLessThan(html.indexOf('param-view'));
    expect(html.indexOf('param-view')).toBeLessThan(html.indexOf('<details'));
    expect(html).toContain('<option value="insulation" selected="">');
    expect(html).toContain('value="3"');
    expect(html).toContain('value="256"');
    expect(html).not.toMatch(/<details[^>]*\bopen/);
    expect(fields[0].key).toBe('executor');
  });
  it('honors optional schema grouping/priority without depending on operator names', () => {
    const groups = groupParameters([{key: 'new_feature', label: 'Feature', type: 'string', priority: -30},
      {key: 'threads', label: 'Threads', type: 'integer', group: 'main'},
      {key: 'custom_flag', label: 'Flag', type: 'boolean', group: 'advanced'}]);
    expect(groups[0].fields.map(field => field.key)).toEqual(['new_feature', 'threads']);
    expect(groups[1].id).toBe('advanced');
  });
});

describe('document execution configuration', () => {
  it('round-trips separate configs and frozen values without mutating another open document', () => {
    const other = structuredClone(graph);
    let next = withExecution(graph, {mode: 'manual', kind: 'ssh', profile_id: 'ssh-a', max_parallel_tasks: 2});
    next = assignNodeTarget(next, 'structure', {kind: 'local'});
    next = withFileLocation(next, 'structure.params.view', {kind: 'local'});
    const loaded = normalizeGraph(JSON.parse(JSON.stringify(next)));
    expect(executionConfig(loaded)).toEqual(executionConfig(next));
    expect(loaded.memory.budget_mb).toBe(400);
    expect(loaded.nodes[0].params).toEqual(graph.nodes[0].params);
    expect(other.runtime).toBeUndefined();
    expect(graph.runtime).toBeUndefined();
    expect(defaultTarget(loaded)).toEqual({kind: 'ssh', profile_id: 'ssh-a'});
    expect(nodeTarget(loaded, 'structure')).toEqual({kind: 'local'});
  });
  it('keeps legacy graphs manual and preserves node/path choices when changing the default', () => {
    let current = assignNodeTarget(graph, 'structure', {kind: 'local'});
    current = withFileLocation(current, 'structure.params.view', {kind: 'ssh', profile_id: 'ssh-a'});
    const next = withExecution(current, {kind: 'ssh', profile_id: 'ssh-a'});
    expect(executionConfig(next).mode).toBe('manual');
    expect(executionConfig(next).node_targets).toEqual({structure: {kind: 'local'}});
    expect(executionConfig(next).file_locations).toEqual(executionConfig(current).file_locations);
  });
  it('treats route nodes atomically and disables all manual menu choices in automatic mode', () => {
    const route = {...structuredClone(graph), nodes: [{...graph.nodes[0], id: 'route', kind: 'route' as const,
      route: {id: 'nested', name: 'Nested', version: 1, graph: structuredClone(graph)}}]};
    const manual = assignNodeTarget(route, 'route', {kind: 'ssh', profile_id: 'ssh-a'});
    expect(nodeTarget(manual, 'route')).toEqual({kind: 'ssh', profile_id: 'ssh-a'});
    expect(manual.nodes[0].route!.graph.runtime).toBeUndefined();
    expect(assignNodeTarget(manual, 'structure', {kind: 'local'})).toBe(manual);
    const automatic = withExecution(manual, {mode: 'auto'});
    expect(assignNodeTarget(automatic, 'route', {kind: 'local'})).toBe(automatic);
    const html = renderToStaticMarkup(<EnvironmentMenu graph={automatic} nodeId="route" servers={servers} onSelect={() => {}}/>);
    expect(html).toContain('整条路线环境');
    expect((html.match(/role="menuitemradio" disabled=""/g) || []).length).toBe(3);
    const manualHtml = renderToStaticMarkup(<EnvironmentMenu graph={manual} nodeId="route" servers={servers} onSelect={() => {}}/>);
    expect(manualHtml).not.toContain('disabled=""');
    expect((manualHtml.match(/aria-checked="true"/g) || []).length).toBe(1);
  });
  it('renders the chosen document mode and default environment', () => {
    const current = withExecution(graph, {mode: 'auto', kind: 'ssh', profile_id: 'ssh-a', max_parallel_tasks: 2});
    const html = renderToStaticMarkup(<ExecutionSettings graph={current} servers={servers} disabled={false} onChange={() => {}}/>);
    expect(html).toContain('aria-pressed="true" class="active">自动');
    expect(html).toContain('<option value="ssh-a" selected="">');
    expect(html).toContain('value="2"');
  });
  it('remaps placement and file metadata on copy/paste, and removes stale assignments after deletion', () => {
    let current = assignNodeTarget(graph, 'structure', {kind: 'ssh', profile_id: 'ssh-a'});
    current = withFileLocation(current, 'structure.params.view', {kind: 'local'});
    const pasted = pasteFragment(current, copyFragment(current, ['structure']));
    expect(executionConfig(pasted.graph).node_targets?.[pasted.ids[0]]).toEqual({kind: 'ssh', profile_id: 'ssh-a'});
    expect(executionConfig(pasted.graph).file_locations?.[`${pasted.ids[0]}.params.view`]).toEqual({kind: 'local'});
    const cleaned = withoutNodeExecution(pasted.graph, ['structure']);
    expect(executionConfig(cleaned).node_targets?.structure).toBeUndefined();
    expect(executionConfig(cleaned).file_locations?.['structure.params.view']).toBeUndefined();
    expect(executionConfig(cleaned).node_targets?.[pasted.ids[0]]).toBeDefined();
  });
});

describe('local and remote inputs', () => {
  it('keeps a local file selector available with an SSH default and shows explicit source locality', () => {
    const source = {id: 'data', kind: 'source' as const, title: 'Data', position: {x: 0, y: 0}, params: {}, input_count: 0,
      source: {path: 'data.csv', dims: ['sample', 'feature'], labels: {}, args: {}, location: {kind: 'local' as const}}};
    const current = withExecution({...graph, nodes: [source]}, {kind: 'ssh', profile_id: 'ssh-a'});
    const catalog: Catalog = {schema_version: 1, operators: [], readers: []};
    const html = renderToStaticMarkup(<Inspector graph={current} catalog={catalog} nodeId="data" settings={false} busy={false}
      servers={servers} uploadLimit={null} onBrowseRemote={() => {}} onNode={() => {}} onMemory={() => {}} onParams={() => {}}
      onDelete={() => {}} onError={() => {}} onClose={() => {}} onOpenRoute={() => {}}/>);
    expect(html).toContain('选择本机文件');
    expect(html).toContain('选择服务器文件');
    expect(html).toContain('本机文件路径');
    expect(html).toContain('<option value="" selected="">本机');
  });
});

describe('parallel task visibility', () => {
  it('maps interleaved stage indexes to explicit canvas nodes and keeps unfinished routes running', () => {
    const events = [
      {event: 'step_started', time: '', index: 1, node_id: 'route'},
      {event: 'step_started', time: '', index: 1, node_id: 'other'},
      {event: 'step_finished', time: '', index: 1, node_id: 'route', node_finished: false},
      {event: 'step_finished', time: '', index: 1, node_id: 'other', node_finished: true},
    ];
    expect(nodeStatuses(events, job)).toEqual({route: 'running', other: 'finished'});
    expect(nodeStatuses([...events, {event: 'step_finished', time: '', index: 3, node_id: 'route', node_finished: true}], job))
      .toEqual({route: 'finished', other: 'finished'});
    expect(nodeStatuses(events, job, true)).toEqual({});
  });
  it('retains legacy 1-based step highlighting and marks completed parent stages', () => {
    const old = {...job, status: 'running' as const, order: ['first', 'second']};
    expect(nodeStatuses([{event: 'step_started', time: '', index: 2}, {event: 'step_finished', time: ''}], old))
      .toEqual({second: 'finished'});
    const parent: Job = {...job, status: 'complete', execution_plan: {mode: 'auto', transfers: [], warnings: [],
      units: [{id: 'stage_1', node_ids: ['route', 'other'], target: {kind: 'local'}, reason: ''}]}};
    expect(nodeStatuses([], parent)).toEqual({route: 'finished', other: 'finished'});
  });
  it('shows all running phases, transfer bytes, individual cancellation, and selectable completed jobs', () => {
    const jobs: Job[] = [job, {...job, id: 'b', name: 'Genome B', status: 'queued', progress: undefined},
      {...job, id: 'c', name: 'Genome C', status: 'running', progress: {phase: 'running', completed: 2, total: 4}},
      {...job, id: 'd', name: 'Genome D', status: 'complete', progress: undefined}];
    const html = renderToStaticMarkup(<TaskManager jobs={jobs} selectedId="c" onSelect={() => {}} onCancel={() => {}} onLogs={() => {}}/>);
    expect(html).toContain('等待资源');
    expect(html).toContain('上传中');
    expect(html).toContain('256 B / 1.00 KiB');
    expect(html).toContain('2 / 4 步');
    expect(html).toContain('max="100" value="25"');
    expect(html).toContain('max="100" value="50"');
    expect((html.match(/aria-label="停止任务/g) || []).length).toBe(3);
    expect((html.match(/aria-label="查看任务/g) || []).length).toBe(4);
    expect(html).not.toContain('disabled=""');
    expect(jobs.filter(isActiveJob)).toHaveLength(3);
    expect(isActiveJob({...job, status: 'preparing'})).toBe(true);
    expect(isActiveJob({...job, status: 'waiting_connection'})).toBe(true);
    expect(isActiveJob({...job, status: 'failed'})).toBe(false);
  });
  it('does not invent percentages while waiting, and bounds server values safely', () => {
    expect(jobPercent({...job, progress: undefined})).toBeUndefined();
    expect(jobPercent({...job, progress: {...job.progress!, percent: 150}})).toBe(100);
    expect(jobPercent({...job, status: 'complete'})).toBe(100);
    const html = renderToStaticMarkup(<TaskProgress job={{...job, status: 'preparing', progress: undefined}}/>);
    expect(html).toContain('准备中');
    expect(html).toContain('<progress');
    expect(html).not.toContain('value=');
  });
});
