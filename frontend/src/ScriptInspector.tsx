import {useEffect, useRef, useState} from 'react';
import {api} from './api';
import {t} from './i18n';
import type {Catalog, GraphNode, NodePatch, Parameter, ScriptSnapshot} from './types';
import {CANONICAL_CATEGORIES, categoryId, categoryLabel} from './operatorPresentation';
import './scriptInspector.css';

type Candidate = {name: string; line: number; schema: Record<string, unknown>};

export function scriptParameters(script: ScriptSnapshot): Parameter[] {
  const properties = script.parameters_schema.properties as Record<string, Record<string, unknown>> | undefined;
  const required = script.parameters_schema.required as string[] | undefined;
  return Object.entries(properties || {}).map(([key, schema]) => ({key,
    label: typeof schema.title === 'string' ? schema.title : key,
    description: typeof schema.description === 'string' ? schema.description : undefined,
    type: Array.isArray(schema.enum) ? 'choice' : schema.type === 'array' || schema.type === 'object' || schema.type === 'null' ? 'json'
      : ['boolean', 'number', 'integer', 'string'].includes(String(schema.type)) ? schema.type as Parameter['type'] : 'json',
    options: Array.isArray(schema.enum) ? schema.enum : undefined,
    min: typeof schema.minimum === 'number' ? schema.minimum : undefined,
    max: typeof schema.maximum === 'number' ? schema.maximum : undefined,
    default: schema.default, required: required?.includes(key) || false,
  }));
}

export function scriptReplacement(current: GraphNode, expectedSha: string, script: ScriptSnapshot, values?: Record<string, unknown>): Partial<GraphNode> {
  if (current.script?.code_sha !== expectedSha) throw Error(t('代码已被其他操作修改，请重新载入后再保存。'));
  return {script, input_count: Object.keys(script.inputs).length,
    ...(values ? {params: {...values, ...current.params}} : {})};
}

/** Code is draft text until an explicit save; source and extracted values commit together. */
export function ScriptInspector({node, disabled, onNode, catalog, onCatalog}: {node: GraphNode; disabled: boolean; onNode: (id: string, patch: NodePatch) => void; catalog?: Catalog; onCatalog?: (catalog: Catalog, createdId?: string) => void}) {
  const script = node.script!;
  const [code, setCode] = useState(script.code);
  const [baseline, setBaseline] = useState(script.code_sha);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const previous = useRef(script);
  useEffect(() => {
    if (script.code_sha !== previous.current.code_sha && baseline !== script.code_sha) {
      if (code === previous.current.code || code === script.code) {setCode(script.code); setBaseline(script.code_sha);}
      else setError(t('代码已被其他操作修改，请重新载入后再保存。'));
      setCandidates([]); setSelected([]);
    }
    previous.current = script;
  }, [script.code_sha]);
  const stale = baseline !== script.code_sha;
  async function save() {
    if (stale) return;
    setWorking(true); setError('');
    try {
      const result = await api.inspectScript({filename: script.filename, code, script});
      onNode(node.id, current => scriptReplacement(current, baseline, result.script));
      setBaseline(result.script.code_sha); setCandidates(result.candidates || []); setSelected([]);
    } catch (reason) {setError((reason as Error).message);}
    finally {setWorking(false);}
  }
  async function extract() {
    setWorking(true); setError('');
    try {
      const result = await api.extractScript({script, names: selected});
      onNode(node.id, current => scriptReplacement(current, script.code_sha, result.script, result.values));
      setCode(result.script.code); setBaseline(result.script.code_sha); setCandidates([]); setSelected([]);
    } catch (reason) {setError((reason as Error).message);}
    finally {setWorking(false);}
  }
  return <section className="script-editor">
    <div className="section-caption"><span>{script.filename}</span><span>{script.language}</span></div>
    <textarea className="mono script-source" aria-label={t('算子代码')} spellCheck={false} value={code} disabled={disabled || working}
      onChange={event => {setCode(event.target.value); setCandidates([]); setSelected([]);}}/>
    <div className="script-actions"><button className="subtle-button" disabled={disabled || working || stale} onClick={() => void save()}>{working ? t('正在检查…') : t('保存代码并检查')}</button>
      {(stale || code !== script.code) && <button className="subtle-button" disabled={working} onClick={() => {setCode(script.code); setBaseline(script.code_sha); setCandidates([]); setSelected([]); setError('');}}>{t('重新载入')}</button>}</div>
    {error && <p className="field-error" role="alert">{error}</p>}
    {!!candidates.length && <div className="script-candidates"><p className="section-caption">{t('选择要提取的参数')}</p>
      {candidates.map(candidate => <label className="check-field" key={candidate.name}><input type="checkbox" disabled={disabled || working}
        checked={selected.includes(candidate.name)} onChange={event => setSelected(values => event.target.checked ? [...values, candidate.name] : values.filter(value => value !== candidate.name))}/>
        <span className="mono">{candidate.name}<small> = {JSON.stringify(candidate.schema.default)}</small></span></label>)}
      <button className="subtle-button" disabled={!selected.length || disabled || working || stale || code !== script.code} onClick={() => void extract()}>{t('提取到参数 JSON')}</button>
    </div>}
    <details className="advanced"><summary>{t('输入输出与依赖')}</summary><pre className="mono script-contract">{JSON.stringify({inputs: script.inputs, outputs: script.outputs, dependencies: script.dependencies}, null, 2)}</pre></details>
    {catalog && onCatalog && <ScriptLibrarySave node={node} catalog={catalog} disabled={disabled || working || stale || code !== script.code} onCatalog={onCatalog}/>}
  </section>;
}

export function ScriptLibrarySave({node, catalog, disabled, onCatalog}: {node: GraphNode; catalog: Catalog; disabled: boolean; onCatalog: (catalog: Catalog, createdId?: string) => void}) {
  const slug = node.script!.filename.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/^[^a-z]+/, '') || 'script';
  const [identifier, setIdentifier] = useState(`user.${slug}`), [category, setCategory] = useState('data');
  const [pending, setPending] = useState(false), [saved, setSaved] = useState(''), [error, setError] = useState('');
  const categories = [...new Set([...CANONICAL_CATEGORIES, ...catalog.operators.map(item => categoryId(item.category))])].filter(value => /^[A-Za-z][A-Za-z0-9_-]*$/.test(value));
  async function save() {
    setPending(true); setError('');
    try {
      const result = await api.publishScript({script: node.script!, operator_id: identifier.trim(), title: node.title, category});
      if (!result.catalog.operators.some(operator => operator.id === result.id)) throw Error(t('算子已保存，但清单尚未包含它，请重新读取算子库。'));
      onCatalog(result.catalog, result.id); setSaved(result.id);
    } catch (reason) {setError((reason as Error).message);} finally {setPending(false);}
  }
  return <details className="advanced"><summary>{t('保存到算子库')}</summary>
    <label className="field"><span>{t('算子 ID')}</span><input value={identifier} placeholder="user.my_filter" disabled={pending} onChange={event => setIdentifier(event.target.value)}/></label>
    <label className="field"><span>{t('算子类别')}</span><select value={category} disabled={pending} onChange={event => setCategory(event.target.value)}>{categories.map(value => <option key={value} value={value}>{t(categoryLabel(value))}</option>)}</select></label>
    <button className="subtle-button" disabled={disabled || pending || !identifier.trim() || saved === identifier.trim()} onClick={() => void save()}>{pending ? t('正在保存…') : t('保存为可复用算子')}</button>
    {saved && <p className="helper" role="status">{t('已添加到算子库：{id}', {id: saved})}</p>}
    {error && <p className="field-error" role="alert">{error}</p>}
  </details>;
}

export function OperatorSource({id, route}: {id?: string; route?: unknown}) {
  const [source, setSource] = useState<{code?: string; available: boolean; reason?: string} | null>(null);
  useEffect(() => {
    let active = true;
    setSource(null);
    if (id) void api.operatorSource(id).then(value => {if (active) setSource(value);}, error => {if (active) setSource({available: false, reason: error.message});});
    return () => {active = false;};
  }, [id]);
  const text = route ? JSON.stringify(route, null, 2) : source?.code;
  return <div className="script-editor"><p className="section-caption">{t('只读源代码')}</p>
    {text ? <textarea className="mono script-source" aria-label={t('只读源代码')} readOnly value={text} spellCheck={false}/>
      : <p className="helper" role="status">{id && !source ? t('正在读取…') : source?.reason || t('此算子未提供可读取的源代码。')}</p>}</div>;
}
