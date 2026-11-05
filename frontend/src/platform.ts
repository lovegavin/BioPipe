import {t} from './i18n';
import {defaultTarget, executionConfig, nodeTarget} from './execution';
import type {Graph, RemoteStatus, TargetRef} from './types';

function systemId(value: string): string {
  const normalized = value.trim().toLowerCase();
  return ({win32: 'windows', win: 'windows', darwin: 'macos', 'mac os': 'macos'} as Record<string, string>)[normalized] || normalized;
}

export function supportedPlatformLabel(systems?: string[]): string {
  if (!systems?.length) return '';
  const values = [...new Set(systems.map(systemId))];
  if (['windows', 'linux', 'macos'].every(value => values.includes(value))) return '';
  const labels: Record<string, string> = {windows: 'Windows', linux: 'Linux', macos: 'macOS'};
  return values.map(value => labels[value] || value).join(' · ');
}

export function supportsTarget(systems: string[] | undefined, target: TargetRef, servers: RemoteStatus[], localSystem?: string): boolean | undefined {
  const system = target.kind === 'ssh'
    ? servers.find(server => server.profile.id === target.profile_id)?.info?.system
    : localSystem;
  if (!systems?.length || !system) return undefined;
  return systems.some(value => systemId(value) === systemId(system));
}

export function targetPlatformWarning(systems: string[] | undefined, graph: Graph, servers: RemoteStatus[], localSystem?: string, nodeId?: string): string {
  // Automatic placement is decided by the planner; the editor OS is irrelevant.
  if (executionConfig(graph).mode === 'auto') return '';
  const target = nodeId ? nodeTarget(graph, nodeId) : defaultTarget(graph);
  return supportsTarget(systems, target, servers, localSystem) === false
    ? t("当前指定的运行环境不支持此算子；需要 {v0}。", {v0: supportedPlatformLabel(systems)}) : '';
}
