import {describe, expect, it} from 'vitest';
import {supportedPlatformLabel, supportsTarget, targetPlatformWarning} from './platform';
import type {Graph, RemoteStatus} from './types';

const servers = [{profile:{id:'server'},info:{system:'Linux'}}] as RemoteStatus[];
const graph: Graph = {schema_version:2,name:'Test',base_dir:'.',nodes:[],edges:[],memory:{enabled:true},
  runtime:{execution:{kind:'ssh',profile_id:'server',mode:'manual'}}};

describe('execution target platform hints', () => {
  it('uses the selected execution host rather than the Windows editor', () => {
    expect(supportsTarget(['linux'],{kind:'ssh',profile_id:'server'},servers,'windows')).toBe(true);
    expect(targetPlatformWarning(['linux'],graph,servers,'windows')).toBe('');
    expect(targetPlatformWarning(['linux'],{...graph,runtime:{execution:{kind:'local',mode:'manual'}}},servers,'windows')).toContain('Linux');
  });
  it('leaves automatic placement and unknown hosts to the runtime planner', () => {
    expect(targetPlatformWarning(['linux'],{...graph,runtime:{execution:{kind:'local',mode:'auto'}}},servers,'windows')).toBe('');
    expect(supportsTarget(['linux'],{kind:'ssh',profile_id:'missing'},servers,'windows')).toBeUndefined();
    expect(supportsTarget(['linux'],{kind:'local'},servers)).toBeUndefined();
  });
  it('respects per-node assignments and normalizes platform aliases', () => {
    const override = {...graph,runtime:{execution:{kind:'ssh',profile_id:'server',mode:'manual',node_targets:{pca:{kind:'local'}}}}};
    expect(targetPlatformWarning(['linux'],override,servers,'windows','pca')).toContain('Linux');
    expect(supportsTarget(['darwin'],{kind:'local'},servers,'macos')).toBe(true);
    expect(supportedPlatformLabel(['windows','darwin','linux'])).toBe('');
    expect(supportedPlatformLabel(['linux','darwin'])).toBe('Linux · macOS');
  });
});
