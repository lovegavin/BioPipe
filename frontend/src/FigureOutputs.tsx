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

export function figureUrl(jobId: string, step: number, format: string) {
  return api.url(`/api/jobs/${encodeURIComponent(jobId)}/exports/${step}/figure?format=${encodeURIComponent(format)}`);
}

export function FigureLinks({jobId, step, formats, compact = false}: {jobId: string; step: number; formats: string[]; compact?: boolean}) {
  return <div className="figure-links" aria-label="已保存图表">
    {formats.map(format => <a key={format} className="text-button" href={figureUrl(jobId, step, format)}
      target="_blank" rel="noreferrer" aria-label={`打开 ${format.toUpperCase()}`}>
      {!compact && <><ArrowSquareOut size={13}/>打开 </>}{format.toUpperCase()}</a>)}
  </div>;
}
