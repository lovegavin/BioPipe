import {ArrowSquareOut} from '@phosphor-icons/react';
import {api} from './api';

const supported = new Set(['png', 'pdf', 'svg', 'jpg', 'jpeg', 'webp', 'tif', 'tiff']);
export function figureFormats(report: Record<string, unknown> | null | undefined): string[] {
  if (!report) return [];
  const formats = Array.isArray(report.figures) ? report.figures.flatMap(item =>
    item && typeof item === 'object' && supported.has(item.format) ? [item.format as string] : []) : [];
  if (formats.length) return [...new Set(formats)].sort((a,b) =>
    ['png','pdf','svg'].indexOf(a) - ['png','pdf','svg'].indexOf(b));
  // Older reports may only contain the original path (enrichment_plot used figure_path).
  const extension = String(report.path || report.figure_path || report.filename || '').split('.').pop()?.toLowerCase();
  return extension && supported.has(extension) ? [extension] : [];
}

export function figureUrl(jobId: string, step: number, format: string, figureId?: string) {
  return api.url(`/api/jobs/${encodeURIComponent(jobId)}/exports/${step}/figure?format=${encodeURIComponent(format)}${figureId === undefined ? "" : `&figure_id=${encodeURIComponent(figureId)}`}`);
}

export function FigureLinks({jobId, step, formats, figureId, compact = false}: {jobId: string; step: number; formats: string[]; figureId?: string; compact?: boolean}) {
  return <div className="figure-links" aria-label="已保存图表">
    {formats.map(format => <a key={format} className="text-button" href={figureUrl(jobId, step, format, figureId)}
      target="_blank" rel="noreferrer" aria-label={`打开 ${format.toUpperCase()}`}>
      {!compact && <><ArrowSquareOut size={13}/>打开 </>}{format.toUpperCase()}</a>)}
  </div>;
}

export function figureGroups(report: Record<string, unknown> | null | undefined): {id: string; title: string; formats: string[]}[] {
  if (!report) return [];
  const groups = new Map<string, {id: string; title: string; formats: string[]}>();
  if (Array.isArray(report.figures)) for (const file of report.figures) {
    if (!file || typeof file !== 'object' || !supported.has(file.format)) continue;
    const id = typeof file.id === 'string' ? file.id : '__legacy__';
    const group = groups.get(id) || {id, title: String(file.title || report.title || report.name || '输出图表'), formats: [] as string[]};
    if (!group.formats.includes(file.format)) group.formats.push(file.format);
    groups.set(id, group);
  }
  if (!groups.size && figureFormats(report).length) return [{id: '__legacy__', title: String(report.title || report.name || '输出图表'), formats: figureFormats(report)}];
  return [...groups.values()];
}

export function FigureGallery({jobId, step, report, focusId}: {jobId: string; step: number; report: Record<string, unknown>; focusId?: string}) {
  return <>{figureGroups(report).filter(group => !focusId || group.id === focusId).map(group => {
    const id = group.id === '__legacy__' ? undefined : group.id;
    const preview = group.formats.find(f => ['png','svg','jpg','jpeg','webp'].includes(f));
    return <section className="figure-preview" key={group.id}>
      <h3>{group.title}</h3>
      {preview && <a className="figure-image-link" href={figureUrl(jobId, step, preview, id)} target="_blank" rel="noreferrer" aria-label={`打开 ${group.title} 原图`}>
        <img loading="lazy" src={figureUrl(jobId, step, preview, id)} alt={group.title}/>
      </a>}
      <FigureLinks jobId={jobId} step={step} formats={group.formats} figureId={id}/>
    </section>;
  })}</>;
}
