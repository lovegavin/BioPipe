import {afterEach, describe, expect, it} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {setLanguage, translate, t} from './i18n';
import zh from './i18n/zh-CN.json';
import en from './i18n/en.json';
import {enumKey, localizeOperator, operatorText} from './operatorLocalization';
import {displayTitle, runSignature} from './graph';
import {ParameterField} from './Inspector';
import {PluginPanel} from './PluginPanel';
import {SettingsPage} from './SettingsPage';
import {AgentPanel} from './AgentPanel';
import type {Graph, Operator} from './types';

afterEach(() => setLanguage('system'));
const operator: Operator = {id:'example.scale', title:'Scale', category:'data', description:'Scale matrix',
  inputs_arity:1, outputs:['scaled'], output_parameter:null, resources:{memory_modes:['full'], supports_cuda:false},
  parameters:[{key:'method', label:'Method', type:'choice', default:'fast', options:['fast', 'accurate']}],
  localization:{default_locale:'en', translations:{en:{title:'Scale'}, zh:{title:'缩放'}, 'zh-CN':{parameters:{method:{title:'方法', enum_labels:{'"fast"':'快速'}}}}}}};

describe('language projections', () => {
  it('has matching dictionaries and interpolation placeholders', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort());
    for (const key of Object.keys(zh) as (keyof typeof zh)[]) {
      expect((en[key].match(/\{\w+\}/g) || []).sort(), key).toEqual((zh[key].match(/\{\w+\}/g) || []).sort());
    }
    expect(translate('en','{count} 个节点',{count:3})).toBe('3 nodes');
    expect(translate('en','unknown')).toBe('unknown');
    expect(translate('en','constructor')).toBe('constructor');
    expect(enumKey(1)).not.toBe(enumKey('1'));
    expect(enumKey({a: 1, b: true})).toBe(enumKey({b: true, a: 1.0}));
  });
  it('switches presentation without changing saved values, ports or custom titles', () => {
    const graph = {schema_version:2, name:'Saved', base_dir:'.', nodes:[{id:'a', kind:'operator', operator:operator.id,
      title:'Scale', params:{method:'fast'}, position:{x:0,y:0}, input_count:1}], edges:[], memory:{enabled:true}} as Graph;
    const signature = runSignature(graph), original = structuredClone(operator);
    const localized = localizeOperator(operator,'zh-CN');
    expect(localized.title).toBe('缩放');
    expect(localized.description).toBe('Scale matrix');
    expect(localized.parameters[0].label).toBe('方法');
    expect(localized.parameters[0].default).toBe('fast');
    expect(localized.outputs).toEqual(['scaled']);
    expect(displayTitle(graph.nodes[0],localized)).toBe('缩放');
    expect(displayTitle({...graph.nodes[0],title:'My label'},localized)).toBe('My label');
    expect(localizeOperator(operator,'fr').title).toBe('Scale');
    expect(runSignature(graph)).toBe(signature); expect(operator).toEqual(original);
    const html=renderToStaticMarkup(<ParameterField field={localized.parameters[0]} value="fast" disabled={false} onChange={()=>{}}/>);
    expect(html).toContain('value="&quot;fast&quot;"'); expect(html).toContain('快速');
  });
  it('keeps v3 declarations in their original language', () => {
    const {localization: _pack, ...v3} = operator;
    expect(localizeOperator(v3,'zh-CN')).toBe(v3);
  });
  it('prefers the exact language even when it is also the default', () => {
    expect(operatorText({default_locale: 'zh-CN', translations: {
      'zh-CN': {title: '精确'}, zh: {title: '通用', description: '说明'}
    }}, 'zh-CN')).toMatchObject({title: '精确', description: '说明'});
  });
  it('provides both library pages, with ordinary and workflow import in Add', () => {
    setLanguage('en');
    const html=renderToStaticMarkup(<PluginPanel initialTab="add" onClose={()=>{}} onChanged={async()=>{}}/>);
    expect(html).toContain('Manage library'); expect(html).toContain('Add operators');
    expect(html).toContain('Operators and Readers'); expect(html).toContain('Workflow operators');
    expect(html).toContain('Import package'); expect(html).toContain('Import workflow file');
    expect(html).toContain('.whl,.operon-library.zip,.biopipe-library.zip'); expect(html).toContain('aria-pressed="true">Add operators');
  });
  it('puts language beside existing settings without remounting server drafts', () => {
    setLanguage('en'); expect(t('设置')).toBe('Settings');
    const html=renderToStaticMarkup(<SettingsPage initial="language" servers={[]} active="" onClose={()=>{}} onSelect={()=>{}} onUpdate={async()=>{}} appearance={{preference:'system',onChange:()=>{}}}/>);
    expect(html).toContain('Interface language'); expect(html).toContain('Server connection');
    expect(html).toContain('Outputs and viewers'); expect(html).toContain('English');
    setLanguage('zh-CN'); expect(t('设置')).toBe('设置');
  });
  it('brands MCP configuration as Operon while retaining an explicitly configured compatible runtime', () => {
    setLanguage('en');
    const fallback = renderToStaticMarkup(<AgentPanel onClose={()=>{}} onCopySelection={()=>{}}/>);
    expect(fallback).toContain('Operon CLI');
    expect(fallback).toContain('&quot;command&quot;: &quot;operon&quot;');
    const configured = renderToStaticMarkup(<AgentPanel command={{command:'python',args:['-m','operon','mcp','--allow-run']}} onClose={()=>{}} onCopySelection={()=>{}}/>);
    expect(configured).toContain('&quot;operon&quot;: {');
    expect(configured).toContain('&quot;command&quot;: &quot;python&quot;');
    expect(configured).toContain('&quot;operon&quot;');
    expect(configured).toContain('The Python module name is retained for compatibility');
  });
});
